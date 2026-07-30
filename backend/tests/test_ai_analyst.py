import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.market import Market
from app.services.ai_analyst import AIAnalystError, analyze_market

VALID_RESPONSE = {
    "market_ticker": "BTC-70K",
    "market_implied_probability": 0.42,
    "ai_estimated_probability": 0.58,
    "edge": 0.16,
    "reasoning": ["BTC momentum increasing", "ETF inflows positive"],
    "risks": ["Macro shock before settlement"],
    "confidence": 8,
    "recommendation": "Consider YES",
    "suggested_allocation_pct": 5,
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


def _mock_openai_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content=content))]
    return response


@pytest.mark.asyncio
async def test_analyze_market_returns_validated_analysis(monkeypatch):
    monkeypatch.setattr("app.services.ai_analyst.settings.openai_api_key", "test-key")

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(
        return_value=_mock_openai_response(json.dumps(VALID_RESPONSE))
    )

    with patch("app.services.ai_analyst.AsyncOpenAI", return_value=fake_client):
        result = await analyze_market(make_market(), [])

    assert result.recommendation == "Consider YES"
    assert result.confidence == 8
    assert result.ai_estimated_probability == 0.58


@pytest.mark.asyncio
async def test_analyze_market_raises_without_api_key(monkeypatch):
    monkeypatch.setattr("app.services.ai_analyst.settings.openai_api_key", None)

    with pytest.raises(AIAnalystError):
        await analyze_market(make_market(), [])


@pytest.mark.asyncio
async def test_analyze_market_raises_on_invalid_json(monkeypatch):
    monkeypatch.setattr("app.services.ai_analyst.settings.openai_api_key", "test-key")

    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(
        return_value=_mock_openai_response("not json")
    )

    with patch("app.services.ai_analyst.AsyncOpenAI", return_value=fake_client):
        with pytest.raises(AIAnalystError):
            await analyze_market(make_market(), [])
