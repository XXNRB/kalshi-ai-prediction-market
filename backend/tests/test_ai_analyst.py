import json
from datetime import datetime
from types import SimpleNamespace
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.market import Market
from app.services.ai_analyst import AIAnalystError, analyze_market, kelly_allocation_pct

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
