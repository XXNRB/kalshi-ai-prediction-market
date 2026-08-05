import pytest
import respx
from httpx import Response

from app.services.kalshi_client import (
    KalshiClient,
    dollars_to_price,
    fixed_point_to_int,
    parse_expiration,
)

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


@pytest.mark.asyncio
async def test_list_markets_flattens_events_and_tags_category():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(
            "/events",
            params={"limit": 10, "status": "open", "with_nested_markets": "true"},
        ).mock(
            return_value=Response(
                200,
                json={
                    "events": [
                        {
                            "category": "Crypto",
                            "event_ticker": "KXBTC-99",
                            "markets": [
                                {"ticker": "BTC-70K", "title": "BTC over 70k"},
                                {"ticker": "BTC-80K", "title": "BTC over 80k"},
                            ],
                        },
                        {
                            "category": "Sports",
                            "event_ticker": "KXNFL-1",
                            "markets": [{"ticker": "NFL-WIN", "title": "Team wins"}],
                        },
                    ]
                },
            )
        )
        client = KalshiClient(base_url=BASE_URL)
        markets = await client.list_markets(limit=10)

    assert len(markets) == 3
    assert markets[0]["ticker"] == "BTC-70K"
    assert markets[0]["category"] == "Crypto"
    assert markets[2]["category"] == "Sports"


def test_dollars_to_price():
    assert dollars_to_price("0.4200") == 0.42
    assert dollars_to_price(None) == 0.0
    assert dollars_to_price("") == 0.0


def test_fixed_point_to_int():
    assert fixed_point_to_int("116739.62") == 116740
    assert fixed_point_to_int(None) == 0


def test_parse_expiration_handles_missing_and_valid():
    assert parse_expiration({}) is None
    dt = parse_expiration({"expiration_time": "2026-08-01T00:00:00Z"})
    assert dt is not None
    assert dt.year == 2026 and dt.month == 8
