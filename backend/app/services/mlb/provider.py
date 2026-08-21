"""Thin, isolated wrapper around statsapi.mlb.com — the same backend
Gameday's own frontend calls (confirmed live against real endpoints, not
scraping). It's undocumented for third-party use, so every other module in
this app reaches MLB data only through this interface, never by calling the
endpoints directly — swapping providers later means implementing this
Protocol again, nothing else changes.

Deliberately dumb: no ticker parsing, no team matching, no caching. Just
"give me the schedule for a date" and "give me the live feed for a game",
returning raw JSON (or None on failure) for services/mlb/mapper.py to turn
into a GameState.
"""

from datetime import date as date_type
from typing import Any, Optional, Protocol

import httpx

from app.config import settings


class MLBProvider(Protocol):
    async def get_schedule(self, for_date: date_type) -> list[dict[str, Any]]:
        """Raw schedule game entries for one date. Empty list on failure —
        callers treat "no games" and "fetch failed" the same way (nothing to
        match), which is the graceful-fallback behavior we want here."""
        ...

    async def get_live_feed(self, game_id: int) -> Optional[dict[str, Any]]:
        """Raw live-feed JSON for one game, or None if unavailable (network
        error, timeout, 404, malformed response)."""
        ...


class StatsAPIMLBProvider:
    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = base_url or settings.mlb_stats_api_base

    async def get_schedule(self, for_date: date_type) -> list[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=settings.mlb_provider_request_timeout_seconds
            ) as client:
                resp = await client.get(
                    "/v1/schedule", params={"sportId": 1, "date": for_date.isoformat()}
                )
                resp.raise_for_status()
                dates = resp.json().get("dates", [])
                return dates[0].get("games", []) if dates else []
        except (httpx.HTTPError, ValueError, KeyError, IndexError):
            return []

    async def get_live_feed(self, game_id: int) -> Optional[dict[str, Any]]:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url, timeout=settings.mlb_provider_request_timeout_seconds
            ) as client:
                resp = await client.get(f"/v1.1/game/{game_id}/feed/live")
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPError, ValueError):
            return None


default_provider = StatsAPIMLBProvider()
