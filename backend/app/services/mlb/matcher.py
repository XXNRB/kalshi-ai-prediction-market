"""Resolves a Kalshi MLB Market to an MLB gamePk exactly once, persists the
result to MLBGameLink, and reuses it forever after — no fuzzy re-matching
every polling cycle.

Matches off the ticker, not the title. Kalshi's MLB ticker format is
`KXMLBGAME-{YY}{MON}{DD}{HHMM}{AWAYCODE}{HOMECODE}-{PICKCODE}`, e.g.
`KXMLBGAME-26AUG061610DETSEA-DET`. AWAYCODE/HOMECODE are concatenated with
no separator and aren't fixed-width (2-3 letters each, e.g. "MINKC" is
3+2), so they're split against a verified static table of official MLB
team codes (checked directly against statsapi.mlb.com/api/v1/teams — the
same codes Kalshi's tickers use), then disambiguated against the pick
segment, which must equal one of the two halves.

Titles are intentionally not used for matching — they're free-text
("Los Angeles A vs Baltimore Winner?") and inherently more ambiguous than
the ticker's own structured codes.
"""

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.market import Market
from app.models.mlb_game_link import MLBGameLink
from app.services.mlb.provider import MLBProvider, default_provider

# Verified against GET https://statsapi.mlb.com/api/v1/teams?sportId=1 —
# the same codes that appear in Kalshi's KXMLBGAME tickers.
TEAM_ID_BY_CODE: dict[str, int] = {
    "ATH": 133, "ATL": 144, "AZ": 109, "BAL": 110, "BOS": 111, "CHC": 112,
    "CIN": 113, "CLE": 114, "COL": 115, "CWS": 145, "DET": 116, "HOU": 117,
    "KC": 118, "LAA": 108, "LAD": 119, "MIA": 146, "MIL": 158, "MIN": 142,
    "NYM": 121, "NYY": 147, "PHI": 143, "PIT": 134, "SD": 135, "SEA": 136,
    "SF": 137, "STL": 138, "TB": 139, "TEX": 140, "TOR": 141, "WSH": 120,
}

_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

_TICKER_RE = re.compile(r"^KXMLBGAME-(\d{2})([A-Z]{3})(\d{2})(\d{4})([A-Z]+)-([A-Z]+)$")

# An unresolved market is retried at most this often, not every polling
# cycle — a market that will never resolve (bad ticker, delisted team)
# shouldn't hammer the schedule endpoint forever.
UNRESOLVED_RETRY_SECONDS = 3600


@dataclass(frozen=True)
class ParsedTicker:
    game_date: date
    away_code: str
    home_code: str
    pick_code: str


def parse_ticker(ticker: str) -> Optional[ParsedTicker]:
    m = _TICKER_RE.match(ticker)
    if not m:
        return None
    yy, mon3, dd, _hhmm, teams_blob, pick_code = m.groups()
    month = _MONTHS.get(mon3)
    if month is None:
        return None
    try:
        game_date = date(2000 + int(yy), month, int(dd))
    except ValueError:
        return None

    codes = _split_team_codes(teams_blob, pick_code)
    if codes is None:
        return None
    away_code, home_code = codes
    return ParsedTicker(game_date=game_date, away_code=away_code, home_code=home_code, pick_code=pick_code)


def _split_team_codes(blob: str, pick_code: str) -> Optional[tuple[str, str]]:
    candidates = [
        (blob[:i], blob[i:])
        for i in range(2, len(blob) - 1)
        if blob[:i] in TEAM_ID_BY_CODE and blob[i:] in TEAM_ID_BY_CODE
    ]
    if not candidates:
        return None
    # The pick segment must be one of the two teams — use it to break ties
    # when the blob could split more than one valid way.
    narrowed = [c for c in candidates if pick_code in c]
    pool = narrowed or candidates
    if len(pool) != 1:
        return None
    return pool[0]


def _find_schedule_candidates(
    games: list[dict[str, Any]], away_id: int, home_id: int
) -> list[dict[str, Any]]:
    return [
        g
        for g in games
        if g.get("teams", {}).get("away", {}).get("team", {}).get("id") == away_id
        and g.get("teams", {}).get("home", {}).get("team", {}).get("id") == home_id
    ]


def _pick_best_candidate(
    candidates: list[dict[str, Any]], kalshi_open_time: Optional[datetime]
) -> tuple[dict[str, Any], str]:
    """Doubleheader tie-break: closest scheduled gameDate to when Kalshi
    opened this market. Falls back to gameNumber 1 (deterministic, not
    guessy) if we have no open_time to compare against."""
    if len(candidates) == 1:
        return candidates[0], "ticker_exact"

    if kalshi_open_time is not None:
        def _delta(g: dict[str, Any]) -> float:
            try:
                game_dt = datetime.fromisoformat(g["gameDate"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                return float("inf")
            open_time = kalshi_open_time
            if open_time.tzinfo is None:
                open_time = open_time.replace(tzinfo=timezone.utc)
            return abs((game_dt - open_time).total_seconds())

        best = min(candidates, key=_delta)
        return best, "ticker_tiebreak_doubleheader"

    for g in candidates:
        if g.get("gameNumber") == 1:
            return g, "ticker_tiebreak_doubleheader"
    return candidates[0], "ticker_tiebreak_doubleheader"


async def resolve_market_game(
    db: Session, market: Market, provider: MLBProvider = default_provider
) -> MLBGameLink:
    """Idempotent: returns the existing link untouched if already resolved,
    only hits the network if unresolved and past the retry throttle."""
    link = db.query(MLBGameLink).filter(MLBGameLink.market_id == market.id).one_or_none()
    now = datetime.utcnow()

    if link is not None and link.mlb_game_id is not None:
        return link

    if link is not None and link.last_attempt_at is not None:
        if (now - link.last_attempt_at).total_seconds() < UNRESOLVED_RETRY_SECONDS:
            return link

    if link is None:
        link = MLBGameLink(market_id=market.id)
        db.add(link)

    link.last_attempt_at = now

    parsed = parse_ticker(market.ticker)
    if parsed is None:
        link.match_method = "unresolved"
        db.commit()
        db.refresh(link)
        return link

    away_id = TEAM_ID_BY_CODE[parsed.away_code]
    home_id = TEAM_ID_BY_CODE[parsed.home_code]

    candidates: list[dict[str, Any]] = []
    for d in (parsed.game_date, parsed.game_date + timedelta(days=1), parsed.game_date - timedelta(days=1)):
        games = await provider.get_schedule(d)
        candidates = _find_schedule_candidates(games, away_id, home_id)
        if candidates:
            break

    if not candidates:
        link.match_method = "unresolved"
        db.commit()
        db.refresh(link)
        return link

    best, method = _pick_best_candidate(candidates, market.kalshi_open_time)
    link.mlb_game_id = best.get("gamePk")
    link.match_method = method
    link.matched_at = now
    db.commit()
    db.refresh(link)
    return link
