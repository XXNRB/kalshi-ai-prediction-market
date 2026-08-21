import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pytest

from app.models.market import Market
from app.models.mlb_game_link import MLBGameLink
from app.services.mlb import matcher
from app.services.mlb.matcher import parse_ticker, resolve_market_game

FIXTURES = Path(__file__).parent / "fixtures"


def _load_schedule(name: str = "mlb_schedule_20260806.json") -> list[dict[str, Any]]:
    return json.loads((FIXTURES / name).read_text())


class StubProvider:
    """Records calls so throttle/idempotency tests can assert on them."""

    def __init__(self, schedule_by_date: dict[date, list[dict[str, Any]]]):
        self.schedule_by_date = schedule_by_date
        self.schedule_calls: list[date] = []

    async def get_schedule(self, for_date: date) -> list[dict[str, Any]]:
        self.schedule_calls.append(for_date)
        return self.schedule_by_date.get(for_date, [])

    async def get_live_feed(self, game_id: int) -> Optional[dict[str, Any]]:
        raise NotImplementedError


def make_market(db_session, ticker: str, kalshi_open_time: Optional[datetime] = None) -> Market:
    market = Market(ticker=ticker, title="Test market", kalshi_open_time=kalshi_open_time)
    db_session.add(market)
    db_session.commit()
    db_session.refresh(market)
    return market


# ---- parse_ticker -----------------------------------------------------------


@pytest.mark.parametrize(
    "ticker,expected_date,expected_away,expected_home,expected_pick",
    [
        ("KXMLBGAME-26AUG061235LAABAL-LAA", date(2026, 8, 6), "LAA", "BAL", "LAA"),
        ("KXMLBGAME-26AUG061240ATHCIN-ATH", date(2026, 8, 6), "ATH", "CIN", "ATH"),
        ("KXMLBGAME-26AUG061310NYMCLE-NYM", date(2026, 8, 6), "NYM", "CLE", "NYM"),
        # "MINKC" splits 3+2 (MIN, KC), not 2+3 or any other combination —
        # the pick segment "-MIN" also confirms which half is which.
        ("KXMLBGAME-26AUG061940MINKC-MIN", date(2026, 8, 6), "MIN", "KC", "MIN"),
        # "DETSEA" splits 3+3.
        ("KXMLBGAME-26AUG061610DETSEA-DET", date(2026, 8, 6), "DET", "SEA", "DET"),
        # "CWSBOS" splits 3+3, and CWS itself is 3 letters overlapping
        # nothing else in the table.
        ("KXMLBGAME-26AUG061910CWSBOS-CWS", date(2026, 8, 6), "CWS", "BOS", "CWS"),
        ("KXMLBGAME-26AUG061420TORCHC-TOR", date(2026, 8, 6), "TOR", "CHC", "TOR"),
    ],
)
def test_parse_ticker_splits_real_examples(ticker, expected_date, expected_away, expected_home, expected_pick):
    parsed = parse_ticker(ticker)
    assert parsed is not None
    assert parsed.game_date == expected_date
    assert parsed.away_code == expected_away
    assert parsed.home_code == expected_home
    assert parsed.pick_code == expected_pick


def test_parse_ticker_rejects_malformed_or_unknown_format():
    assert parse_ticker("KXBTC-26AUG06-T50000") is None
    assert parse_ticker("not-a-ticker") is None


# ---- resolve_market_game ------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_market_game_happy_path(db_session):
    schedule = _load_schedule()
    provider = StubProvider({date(2026, 8, 6): schedule})
    market = make_market(db_session, "KXMLBGAME-26AUG061610DETSEA-DET")

    link = await resolve_market_game(db_session, market, provider)

    assert link.mlb_game_id == 823105  # DET @ SEA from the fixture
    assert link.match_method == "ticker_exact"
    assert link.matched_at is not None


@pytest.mark.asyncio
async def test_resolve_market_game_is_idempotent_and_reused(db_session):
    schedule = _load_schedule()
    provider = StubProvider({date(2026, 8, 6): schedule})
    market = make_market(db_session, "KXMLBGAME-26AUG061610DETSEA-DET")

    first = await resolve_market_game(db_session, market, provider)
    calls_after_first = len(provider.schedule_calls)
    second = await resolve_market_game(db_session, market, provider)

    assert second.id == first.id
    assert second.mlb_game_id == first.mlb_game_id
    # Already resolved -> no new network call at all.
    assert len(provider.schedule_calls) == calls_after_first


@pytest.mark.asyncio
async def test_resolve_market_game_unresolved_throttles_retries(db_session):
    provider = StubProvider({})  # no games anywhere -> always unresolved
    market = make_market(db_session, "KXMLBGAME-26AUG061610DETSEA-DET")

    first = await resolve_market_game(db_session, market, provider)
    assert first.mlb_game_id is None
    assert first.match_method == "unresolved"
    calls_after_first = len(provider.schedule_calls)

    # Immediately retrying should be throttled -- no new network calls.
    second = await resolve_market_game(db_session, market, provider)
    assert second.mlb_game_id is None
    assert len(provider.schedule_calls) == calls_after_first

    # Once the throttle window has passed, it tries again.
    link = db_session.query(MLBGameLink).filter(MLBGameLink.market_id == market.id).one()
    link.last_attempt_at = datetime.utcnow() - timedelta(seconds=matcher.UNRESOLVED_RETRY_SECONDS + 1)
    db_session.commit()

    third = await resolve_market_game(db_session, market, provider)
    assert len(provider.schedule_calls) > calls_after_first
    assert third.mlb_game_id is None


@pytest.mark.asyncio
async def test_resolve_market_game_doubleheader_tiebreak_by_closest_open_time(db_session):
    away_id, home_id = 116, 136  # DET @ SEA, matching the ticker below
    game_1 = {
        "gamePk": 111,
        "gameDate": "2026-08-06T18:00:00Z",
        "gameNumber": 1,
        "teams": {"away": {"team": {"id": away_id}}, "home": {"team": {"id": home_id}}},
    }
    game_2 = {
        "gamePk": 222,
        "gameDate": "2026-08-06T23:00:00Z",
        "gameNumber": 2,
        "teams": {"away": {"team": {"id": away_id}}, "home": {"team": {"id": home_id}}},
    }
    provider = StubProvider({date(2026, 8, 6): [game_1, game_2]})
    # Kalshi opened this market close to game 2's start time.
    open_time = datetime(2026, 8, 6, 22, 30, 0)
    market = make_market(db_session, "KXMLBGAME-26AUG061610DETSEA-DET", kalshi_open_time=open_time)

    link = await resolve_market_game(db_session, market, provider)

    assert link.mlb_game_id == 222
    assert link.match_method == "ticker_tiebreak_doubleheader"


@pytest.mark.asyncio
async def test_resolve_market_game_malformed_ticker_marks_unresolved_without_network_call(db_session):
    provider = StubProvider({})
    market = make_market(db_session, "KXMLBGAME-not-a-real-ticker")

    link = await resolve_market_game(db_session, market, provider)

    assert link.mlb_game_id is None
    assert link.match_method == "unresolved"
    assert provider.schedule_calls == []
