import pytest
import respx
from httpx import Response

from app.services.kalshi_client import KalshiClient, cents_to_price, parse_expiration

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


@pytest.mark.asyncio
async def test_list_markets_parses_response():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/markets", params={"limit": 10, "status": "open"}).mock(
            return_value=Response(
                200,
                json={"markets": [{"ticker": "BTC-70K", "title": "BTC over 70k"}]},
            )
        )
        client = KalshiClient(base_url=BASE_URL)
        markets = await client.list_markets(limit=10)

    assert len(markets) == 1
    assert markets[0]["ticker"] == "BTC-70K"


@pytest.mark.asyncio
async def test_get_market_history():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/markets/BTC-70K/history", params={"limit": 100}).mock(
            return_value=Response(200, json={"history": [{"yes_price": 42}]})
        )
        client = KalshiClient(base_url=BASE_URL)
        history = await client.get_market_history("BTC-70K")

    assert history == [{"yes_price": 42}]


def test_cents_to_price():
    assert cents_to_price(42) == 0.42
    assert cents_to_price(None) == 0.0


def test_parse_expiration_handles_missing_and_valid():
    assert parse_expiration({}) is None
    dt = parse_expiration({"expiration_time": "2026-08-01T00:00:00Z"})
    assert dt is not None
    assert dt.year == 2026 and dt.month == 8
