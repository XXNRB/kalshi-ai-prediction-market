import json

from openai import AsyncOpenAI
from pydantic import ValidationError

from app.config import settings
from app.models.market import Market
from app.models.price_history import PriceHistory
from app.schemas.analysis import MarketAnalysis

SYSTEM_PROMPT = """You are Agent 1, a Research Analyst for a Kalshi prediction-market \
research tool. You are a market researcher, news analyst, and probability analyst. \
Given a market and its recent price history, estimate the true probability of the \
event, compare it against the market-implied probability, and explain your reasoning. \
This is a decision-support tool, not financial advice: be explicit about uncertainty, \
name concrete risks, and never claim higher confidence than the evidence supports. \
Respond with ONLY a JSON object matching this schema (no markdown fences):
{
  "market_ticker": string,
  "market_implied_probability": number (0-1),
  "ai_estimated_probability": number (0-1),
  "edge": number (ai_estimated_probability - market_implied_probability),
  "reasoning": string[] (bullet points),
  "risks": string[] (bullet points),
  "confidence": integer (1-10),
  "recommendation": string (e.g. "Consider YES", "Consider NO", "No clear edge"),
  "suggested_allocation_pct": number (0-100, % of bankroll, conservative),
  "data_sources": string[] (what you based this on, e.g. "Kalshi price history", \
"general knowledge as of training cutoff" - be honest if you have no live news access)
}"""


class AIAnalystError(RuntimeError):
    pass


def build_user_prompt(market: Market, history: list[PriceHistory]) -> str:
    recent = history[-10:]
    history_lines = "\n".join(
        f"- {p.timestamp.isoformat()}: YES={p.yes_price:.2f} NO={p.no_price:.2f} vol={p.volume}"
        for p in recent
    ) or "No historical price data available yet."

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

Estimate the true probability and produce your analysis."""


async def analyze_market(market: Market, history: list[PriceHistory]) -> MarketAnalysis:
    if not settings.openai_api_key:
        raise AIAnalystError(
            "OPENAI_API_KEY is not configured. Set it in backend/.env to enable AI analysis."
        )

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(market, history)},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
    )

    raw_content = response.choices[0].message.content
    try:
        data = json.loads(raw_content)
        return MarketAnalysis.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise AIAnalystError(f"AI response failed validation: {exc}") from exc
