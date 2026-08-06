import json
import logging
from typing import Optional

from openai import AsyncOpenAI
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.models.market import Market
from app.models.price_history import PriceHistory
from app.schemas.analysis import MarketAnalysis

MIN_EDGE_TO_BET = 0.05
MIN_CONFIDENCE_TO_BET = 5

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Agent 1, a Research Analyst for a Kalshi prediction-market \
research tool. You are a market researcher, news analyst, and probability analyst. \
Given a market, its recent price history, and (when available) live web research \
findings, estimate the true probability of the event, compare it against the \
market-implied probability, and explain your reasoning. This is a decision-support \
tool, not financial advice: be explicit about uncertainty, name concrete risks, and \
never claim higher confidence than the evidence supports.

Grounding rules:
- If WEB RESEARCH FINDINGS are provided below, base your reasoning bullets on the \
concrete facts, data points, and named sources in them. Cite the source by name in \
the bullet (e.g. "Reuters reports ..."). Do not invent facts not present in the findings.
- List every source you actually relied on in `data_sources`, using its real title \
(e.g. "Reuters: Fed holds rates steady"), not a generic label.
- If no web research findings are provided, or they're irrelevant to this market, say \
so plainly in `data_sources` (e.g. "No relevant live web sources found — reasoning \
based on general knowledge only") and keep `confidence` low (3 or below) — untethered \
speculation should never be presented as confident analysis.
- Give your best rough `suggested_allocation_pct` (0-100), but know that the app will \
recompute the final figure itself from your probability estimate, the market price, \
and your confidence using a risk-managed position-sizing formula — so focus your \
effort on getting the probability estimate and reasoning right, not this number.

Respond with ONLY a JSON object matching this schema (no markdown fences):
{
  "market_ticker": string,
  "market_implied_probability": number (0-1),
  "ai_estimated_probability": number (0-1),
  "edge": number (ai_estimated_probability - market_implied_probability),
  "reasoning": string[] (bullet points, each grounded in a specific fact or source),
  "risks": string[] (bullet points),
  "confidence": integer (1-10),
  "recommendation": string (e.g. "Consider YES", "Consider NO", "No clear edge"),
  "suggested_allocation_pct": number (0-100, rough estimate, will be recalculated),
  "data_sources": string[] (real source titles used, or an honest note that none were found)
}"""


class AIAnalystError(RuntimeError):
    pass


def build_user_prompt(
    market: Market,
    history: list[PriceHistory],
    research_text: str = "",
) -> str:
    recent = history[-10:]
    history_lines = "\n".join(
        f"- {p.timestamp.isoformat()}: YES={p.yes_price:.2f} NO={p.no_price:.2f} vol={p.volume}"
        for p in recent
    ) or "No historical price data available yet."

    research_section = (
        f"\nWEB RESEARCH FINDINGS:\n{research_text}\n"
        if research_text
        else "\nWEB RESEARCH FINDINGS: none available for this query.\n"
    )

    return f"""Market: {market.title} ({market.ticker})
Category: {market.category or "unknown"}
Description: {market.description or "n/a"}
Current YES price: {market.yes_price:.2f} (implied probability {market.yes_price:.0%})
Current NO price: {market.no_price:.2f}
Volume: {market.volume}
Open interest: {market.open_interest}
Expiration: {market.expiration_date.isoformat() if market.expiration_date else "unknown"}

Recent price history:
{history_lines}
{research_section}
Estimate the true probability and produce your analysis."""


async def gather_research(client: AsyncOpenAI, market: Market) -> tuple[str, list[dict[str, str]]]:
    """Use OpenAI's hosted web_search tool to pull real, current information
    relevant to the market question. Degrades gracefully (empty results) if
    the search step fails, so a flaky search never blocks the analysis."""
    try:
        response = await client.responses.create(
            model=settings.openai_model,
            tools=[{"type": "web_search"}],
            input=(
                "Research current news, data, and expert commentary relevant to this "
                "prediction market question. Prioritize concrete, recent, named sources "
                "over speculation.\n\n"
                f"Market question: {market.title}\n"
                f"Category: {market.category or 'unknown'}\n"
                f"Context: {market.description or 'n/a'}"
            ),
        )
    except Exception:
        logger.warning("Web research step failed; falling back to model knowledge only", exc_info=True)
        return "", []

    text = getattr(response, "output_text", "") or ""
    citations: list[dict[str, str]] = []
    for item in getattr(response, "output", []) or []:
        if getattr(item, "type", None) != "message":
            continue
        for content in getattr(item, "content", []) or []:
            for annotation in getattr(content, "annotations", []) or []:
                if getattr(annotation, "type", None) == "url_citation":
                    citations.append(
                        {"title": getattr(annotation, "title", "") or annotation.url, "url": annotation.url}
                    )
    return text, citations


def kelly_allocation_pct(
    ai_probability: float,
    market_yes_price: float,
    confidence: int,
    kelly_fraction: float = 0.25,
    max_allocation_pct: float = 15.0,
) -> float:
    """Risk-managed position size: fractional Kelly (quarter-Kelly) on
    whichever side has positive edge, further scaled down by the model's
    own stated confidence, and capped at max_allocation_pct. This replaces
    whatever number the LLM proposed so allocation actually tracks edge and
    confidence instead of defaulting to a generic figure every time."""
    if ai_probability >= market_yes_price:
        p, price = ai_probability, market_yes_price
    else:
        p, price = 1 - ai_probability, 1 - market_yes_price

    if price <= 0 or price >= 1:
        return 0.0

    full_kelly = (p - price) / (1 - price)
    if full_kelly <= 0:
        return 0.0

    confidence_scalar = max(min(confidence, 10), 0) / 10
    allocation = full_kelly * kelly_fraction * confidence_scalar * 100
    return round(min(allocation, max_allocation_pct), 1)


class AllocationResult(BaseModel):
    raw_allocation_pct: float
    final_allocation_pct: float
    skipped: bool
    skip_reason: Optional[str] = None


def allocate_batch(
    analyses: dict[str, MarketAnalysis], max_allocation_pct: float = 15.0
) -> dict[str, AllocationResult]:
    """Cross-market position sizing on top of the existing per-market
    kelly_allocation_pct: markets below a conviction threshold (weak edge
    or low confidence) are skipped entirely rather than just shrunk, and
    the capital that would have gone to them is redistributed
    proportionally to the remaining markets' own raw Kelly share, still
    capped at max_allocation_pct per market."""
    raw = {
        ticker: kelly_allocation_pct(
            a.ai_estimated_probability, a.market_implied_probability, a.confidence, max_allocation_pct=max_allocation_pct
        )
        for ticker, a in analyses.items()
    }

    skip_reasons: dict[str, str] = {}
    for ticker, a in analyses.items():
        if abs(a.edge) < MIN_EDGE_TO_BET:
            skip_reasons[ticker] = (
                f"Edge of {a.edge:+.0%} is below the {MIN_EDGE_TO_BET:.0%} conviction threshold — too close to a toss-up."
            )
        elif a.confidence < MIN_CONFIDENCE_TO_BET:
            skip_reasons[ticker] = (
                f"Confidence {a.confidence}/10 is below the {MIN_CONFIDENCE_TO_BET}/10 threshold."
            )

    freed = sum(raw[t] for t in skip_reasons)
    kept = [t for t in analyses if t not in skip_reasons]
    kept_raw_total = sum(raw[t] for t in kept)

    results: dict[str, AllocationResult] = {}
    for ticker, reason in skip_reasons.items():
        results[ticker] = AllocationResult(
            raw_allocation_pct=raw[ticker], final_allocation_pct=0.0, skipped=True, skip_reason=reason
        )
    for ticker in kept:
        boost = freed * (raw[ticker] / kept_raw_total) if kept_raw_total > 0 else 0.0
        final = round(min(raw[ticker] + boost, max_allocation_pct), 1)
        results[ticker] = AllocationResult(
            raw_allocation_pct=raw[ticker], final_allocation_pct=final, skipped=False
        )
    return results


async def analyze_market(market: Market, history: list[PriceHistory]) -> MarketAnalysis:
    if not settings.openai_api_key:
        raise AIAnalystError(
            "OPENAI_API_KEY is not configured. Set it in backend/.env to enable AI analysis."
        )

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    research_text, citations = await gather_research(client, market)
    if citations:
        sources_list = "\n".join(f"- {c['title']}: {c['url']}" for c in citations)
        research_text = f"{research_text}\n\nSources:\n{sources_list}"

    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(market, history, research_text)},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw_content = response.choices[0].message.content
    try:
        data = json.loads(raw_content)
        analysis = MarketAnalysis.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AIAnalystError(f"AI response failed validation: {exc}") from exc

    sized_allocation = kelly_allocation_pct(
        analysis.ai_estimated_probability, market.yes_price, analysis.confidence
    )
    return analysis.model_copy(update={"suggested_allocation_pct": sized_allocation})
