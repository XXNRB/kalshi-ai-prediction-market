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
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as client:
            resp = await client.get("/markets", params={"limit": limit, "status": status})
            resp.raise_for_status()
            return resp.json().get("markets", [])

    async def get_market(self, ticker: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as client:
            resp = await client.get(f"/markets/{ticker}")
            resp.raise_for_status()
            return resp.json().get("market", {})

    async def get_market_history(
        self, ticker: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=15.0) as client:
            resp = await client.get(f"/markets/{ticker}/history", params={"limit": limit})
            resp.raise_for_status()
            return resp.json().get("history", [])


def parse_expiration(raw: dict[str, Any]) -> Optional[datetime]:
    value = raw.get("expiration_time") or raw.get("close_time")
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def cents_to_price(cents: Optional[int]) -> float:
    return round((cents or 0) / 100, 4)
