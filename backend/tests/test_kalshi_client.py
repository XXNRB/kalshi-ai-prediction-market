import pytest
import respx
from httpx import Response

from app.services.kalshi_client import (
    KalshiClient,
    dollars_to_price,
    fixed_point_to_int,
    parse_candlestick,
    parse_expiration,
    parse_open_time,
)

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"


@pytest.mark.asyncio
async def test_list_markets_flattens_events_and_tags_category_and_series():
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
                            "series_ticker": "KXBTC",
                            "markets": [
                                {"ticker": "BTC-70K", "title": "BTC over 70k"},
                                {"ticker": "BTC-80K", "title": "BTC over 80k"},
                            ],
                        },
                        {
                            "category": "Sports",
                            "event_ticker": "KXNFL-1",
                            "series_ticker": "KXNFL",
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
    assert markets[0]["series_ticker"] == "KXBTC"
    assert markets[2]["category"] == "Sports"
    assert markets[2]["series_ticker"] == "KXNFL"


@pytest.mark.asyncio
async def test_get_candlesticks_hits_correct_url():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get(
            "/series/KXBTC/markets/BTC-70K/candlesticks",
            params={"start_ts": 1000, "end_ts": 2000, "period_interval": 1},
        ).mock(return_value=Response(200, json={"candlesticks": [{"end_period_ts": 1500}]}))

        client = KalshiClient(base_url=BASE_URL)
        candles = await client.get_candlesticks("KXBTC", "BTC-70K", 1000, 2000, period_interval=1)

    assert candles == [{"end_period_ts": 1500}]


def test_parse_candlestick():
    point = parse_candlestick(
        {
            "end_period_ts": 1785888000,
            "yes_bid": {"close_dollars": "0.4200"},
            "volume_fp": "12.00",
        }
    )
    assert point["yes_price"] == 0.42
    assert point["no_price"] == 0.58
    assert point["volume"] == 12
    assert point["timestamp"].year >= 2026


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


def test_parse_open_time_prefers_open_time_over_created_time():
    assert parse_open_time({}) is None
    dt = parse_open_time({"open_time": "2025-08-28T20:45:00Z", "created_time": "2025-08-01T00:00:00Z"})
    assert dt is not None
    assert dt.month == 8 and dt.day == 28
    fallback = parse_open_time({"created_time": "2025-08-01T00:00:00Z"})
    assert fallback is not None and fallback.day == 1
