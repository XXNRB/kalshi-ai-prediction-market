import json
from datetime import datetime
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.market import Market
from app.schemas.analysis import MarketAnalysis
from app.services.ai_analyst import AIAnalystError, allocate_batch, analyze_market, kelly_allocation_pct

VALID_RESPONSE = {
    "market_ticker": "BTC-70K",
    "market_implied_probability": 0.42,
    "ai_estimated_probability": 0.58,
    "edge": 0.16,
    "reasoning": ["BTC momentum increasing", "ETF inflows positive"],
    "risks": ["Macro shock before settlement"],
    "confidence": 8,
    "recommendation": "Consider YES",
    "suggested_allocation_pct": 50,  # deliberately implausible to prove it gets overridden
    "data_sources": ["Kalshi price history"],
}


def make_market() -> Market:
    return Market(
        id=1,
        ticker="BTC-70K",
        title="Will BTC exceed $70,000 by Friday?",
        category="Crypto",
        description=None,
        yes_price=0.42,
        no_price=0.58,
        volume=1000,
        open_interest=500,
        liquidity=0.0,
        expiration_date=datetime(2026, 8, 1),
    )


def _mock_chat_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


def _mock_web_search_response(text: str = "", citations: Optional[list] = None):
    citations = citations or []
    annotations = [
        SimpleNamespace(type="url_citation", title=c["title"], url=c["url"]) for c in citations
    ]
    content = SimpleNamespace(type="output_text", text=text, annotations=annotations)
    message = SimpleNamespace(type="message", content=[content])
    return SimpleNamespace(output_text=text, output=[message])


@pytest.mark.asyncio
async def test_analyze_market_returns_validated_analysis(monkeypatch):
    monkeypatch.setattr("app.services.ai_analyst.settings.openai_api_key", "test-key")

    fake_client = MagicMock()
    fake_client.responses.create = AsyncMock(
        return_value=_mock_web_search_response(
            "BTC ETF inflows hit a record this week.",
            [{"title": "Reuters: BTC ETF inflows surge", "url": "https://reuters.com/btc"}],
        )
    )
    fake_client.chat.completions.create = AsyncMock(
        return_value=_mock_chat_response(json.dumps(VALID_RESPONSE))
    )

    with patch("app.services.ai_analyst.AsyncOpenAI", return_value=fake_client):
        result = await analyze_market(make_market(), [])

    assert result.recommendation == "Consider YES"
    assert result.confidence == 8
    assert result.ai_estimated_probability == 0.58

    # allocation must be recomputed from edge/confidence, not the LLM's raw 50
    expected = kelly_allocation_pct(0.58, 0.42, 8)
    assert result.suggested_allocation_pct == expected
    assert result.suggested_allocation_pct != 50

    # the research prompt actually reached the synthesis call
    sent_prompt = fake_client.chat.completions.create.call_args.kwargs["messages"][1]["content"]
    assert "Reuters: BTC ETF inflows surge" in sent_prompt


@pytest.mark.asyncio
async def test_analyze_market_degrades_gracefully_when_web_search_fails(monkeypatch):
    monkeypatch.setattr("app.services.ai_analyst.settings.openai_api_key", "test-key")

    fake_client = MagicMock()
    fake_client.responses.create = AsyncMock(side_effect=RuntimeError("search unavailable"))
    fake_client.chat.completions.create = AsyncMock(
        return_value=_mock_chat_response(json.dumps(VALID_RESPONSE))
    )

    with patch("app.services.ai_analyst.AsyncOpenAI", return_value=fake_client):
        result = await analyze_market(make_market(), [])

    assert result.recommendation == "Consider YES"


@pytest.mark.asyncio
async def test_analyze_market_raises_without_api_key(monkeypatch):
    monkeypatch.setattr("app.services.ai_analyst.settings.openai_api_key", None)

    with pytest.raises(AIAnalystError):
        await analyze_market(make_market(), [])


@pytest.mark.asyncio
async def test_analyze_market_raises_on_invalid_json(monkeypatch):
    monkeypatch.setattr("app.services.ai_analyst.settings.openai_api_key", "test-key")

    fake_client = MagicMock()
    fake_client.responses.create = AsyncMock(return_value=_mock_web_search_response())
    fake_client.chat.completions.create = AsyncMock(
        return_value=_mock_chat_response("not json")
    )

    with patch("app.services.ai_analyst.AsyncOpenAI", return_value=fake_client):
        with pytest.raises(AIAnalystError):
            await analyze_market(make_market(), [])


def test_kelly_allocation_scales_with_edge_and_confidence():
    small_edge = kelly_allocation_pct(ai_probability=0.45, market_yes_price=0.42, confidence=8)
    large_edge = kelly_allocation_pct(ai_probability=0.75, market_yes_price=0.42, confidence=8)
    assert 0 < small_edge < large_edge


def test_kelly_allocation_scales_with_confidence():
    low_confidence = kelly_allocation_pct(ai_probability=0.75, market_yes_price=0.42, confidence=2)
    high_confidence = kelly_allocation_pct(ai_probability=0.75, market_yes_price=0.42, confidence=10)
    assert 0 < low_confidence < high_confidence


def test_kelly_allocation_zero_when_no_edge():
    # AI's estimate exactly matches the market price on both sides -> no edge either way
    assert kelly_allocation_pct(ai_probability=0.42, market_yes_price=0.42, confidence=9) == 0.0


def test_kelly_allocation_caps_at_max():
    allocation = kelly_allocation_pct(
        ai_probability=0.99, market_yes_price=0.05, confidence=10, max_allocation_pct=15.0
    )
    assert allocation == 15.0


def test_kelly_allocation_handles_no_side_edge():
    # market overprices YES (0.80) but AI thinks it's much less likely (0.30) -> bet NO
    allocation = kelly_allocation_pct(ai_probability=0.30, market_yes_price=0.80, confidence=9)
    assert allocation > 0


def make_analysis(**overrides) -> MarketAnalysis:
    defaults = dict(
        market_ticker="TICKER",
        market_implied_probability=0.42,
        ai_estimated_probability=0.58,
        edge=0.16,
        reasoning=["reason"],
        risks=["risk"],
        confidence=8,
        recommendation="Consider YES",
        suggested_allocation_pct=0.0,
        data_sources=["source"],
    )
    defaults.update(overrides)
    return MarketAnalysis(**defaults)


def test_allocate_batch_skips_weak_edge_and_boosts_the_strong_pick():
    analyses = {
        "STRONG": make_analysis(
            market_implied_probability=0.40, ai_estimated_probability=0.60, edge=0.20, confidence=8
        ),
        "WEAK": make_analysis(
            market_implied_probability=0.50, ai_estimated_probability=0.52, edge=0.02, confidence=6
        ),
    }

    results = allocate_batch(analyses)

    assert results["WEAK"].skipped is True
    assert results["WEAK"].final_allocation_pct == 0.0
    assert "conviction threshold" in results["WEAK"].skip_reason

    assert results["STRONG"].skipped is False
    assert results["STRONG"].final_allocation_pct > results["STRONG"].raw_allocation_pct


def test_allocate_batch_skips_low_confidence_even_with_decent_edge():
    analyses = {
        "UNSURE": make_analysis(
            market_implied_probability=0.40, ai_estimated_probability=0.55, edge=0.15, confidence=3
        ),
    }

    results = allocate_batch(analyses)

    assert results["UNSURE"].skipped is True
    assert "Confidence" in results["UNSURE"].skip_reason


def test_allocate_batch_never_exceeds_cap_even_after_redistribution():
    analyses = {
        "MAXED": make_analysis(
            market_implied_probability=0.05, ai_estimated_probability=0.99, edge=0.94, confidence=10
        ),
        "SKIPPED": make_analysis(
            market_implied_probability=0.50, ai_estimated_probability=0.52, edge=0.02, confidence=9
        ),
    }

    results = allocate_batch(analyses, max_allocation_pct=15.0)

    assert results["MAXED"].raw_allocation_pct == 15.0
    assert results["MAXED"].final_allocation_pct == 15.0  # freed capital has nowhere left to go


def test_allocate_batch_redistributes_freed_capital_proportionally():
    analyses = {
        "A": make_analysis(
            market_implied_probability=0.42, ai_estimated_probability=0.55, edge=0.13, confidence=6
        ),
        "B": make_analysis(
            market_implied_probability=0.42, ai_estimated_probability=0.50, edge=0.08, confidence=6
        ),
        "C": make_analysis(
            market_implied_probability=0.42, ai_estimated_probability=0.44, edge=0.02, confidence=6
        ),
    }

    results = allocate_batch(analyses)

    assert results["C"].skipped is True
    boost_a = results["A"].final_allocation_pct - results["A"].raw_allocation_pct
    boost_b = results["B"].final_allocation_pct - results["B"].raw_allocation_pct
    assert boost_a > 0
    assert boost_b > 0
    # freed capital from C should roughly land on A and B combined (allowing for per-step rounding)
    assert boost_a + boost_b == pytest.approx(results["C"].raw_allocation_pct, abs=0.2)
