from datetime import datetime
from typing import Any, Optional

import httpx

from app.config import settings


class KalshiClient:
    """Thin wrapper around Kalshi's public (unauthenticated) market-data
    endpoints. Order placement is out of scope until real-money trading
    is explicitly enabled in a later phase."""

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or settings.kalshi_api_base

    async def list_markets(self, limit: int = 50, status: str = "open") -> list[dict[str, Any]]:
        """Fetch open events with their nested markets and flatten into a
        list of market dicts, each tagged with its parent event's category.

        Kalshi's plain /markets endpoint mixes in exotic multivariate combo
        products with garbled titles and no category; /events with nested
        markets is where clean category + title data actually lives."""
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as client:
            resp = await client.get(
                "/events",
                params={"limit": limit, "status": status, "with_nested_markets": "true"},
            )
            resp.raise_for_status()
            events = resp.json().get("events", [])

        markets: list[dict[str, Any]] = []
        for event in events:
            category = event.get("category")
            series_ticker = event.get("series_ticker")
            for market in event.get("markets", []):
                market["category"] = category
                market["series_ticker"] = series_ticker
                markets.append(market)
        return markets

    async def get_candlesticks(
        self,
        series_ticker: str,
        ticker: str,
        start_ts: int,
        end_ts: int,
        period_interval: int = 60,
    ) -> list[dict[str, Any]]:
        """Fetch real historical candlesticks for one market. period_interval
        is in minutes; Kalshi only accepts 1, 60, or 1440."""
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as client:
            resp = await client.get(
                f"/series/{series_ticker}/markets/{ticker}/candlesticks",
                params={"start_ts": start_ts, "end_ts": end_ts, "period_interval": period_interval},
            )
            resp.raise_for_status()
            return resp.json().get("candlesticks", [])


def parse_kalshi_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def parse_expiration(raw: dict[str, Any]) -> Optional[datetime]:
    return parse_kalshi_datetime(raw.get("expiration_time") or raw.get("close_time"))


def parse_open_time(raw: dict[str, Any]) -> Optional[datetime]:
    return parse_kalshi_datetime(raw.get("open_time") or raw.get("created_time"))


def dollars_to_price(value: Optional[str]) -> float:
    """Kalshi's public API returns prices as decimal-dollar strings, e.g. "0.4200"."""
    if not value:
        return 0.0
    try:
        return round(float(value), 4)
    except ValueError:
        return 0.0


def fixed_point_to_int(value: Optional[str]) -> int:
    """Volume/open interest come back as fixed-point decimal strings, e.g. "116739.62"."""
    if not value:
        return 0
    try:
        return int(round(float(value)))
    except ValueError:
        return 0


def parse_candlestick(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert one Kalshi candlestick into our PricePoint shape."""
    yes_price = dollars_to_price((raw.get("yes_bid") or {}).get("close_dollars"))
    return {
        "timestamp": datetime.utcfromtimestamp(raw["end_period_ts"]),
        "yes_price": yes_price,
        "no_price": round(1 - yes_price, 4),
        "volume": fixed_point_to_int(raw.get("volume_fp")),
    }
