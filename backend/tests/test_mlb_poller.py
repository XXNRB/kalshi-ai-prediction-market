import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pytest

from app.models.market import Market
from app.models.mlb_game_state_snapshot import MLBGameStateSnapshot
from app.models.trade import Trade
from app.services.mlb import cache
from app.services.mlb.poller import run_mlb_poll_cycle
from app.services import portfolio as portfolio_service

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


class StubProvider:
    def __init__(self, schedule_by_date: dict[date, list[dict]], live_feed_by_id: dict[int, Optional[dict]]):
        self.schedule_by_date = schedule_by_date
        self.live_feed_by_id = live_feed_by_id
        self.live_feed_calls: list[int] = []

    async def get_schedule(self, for_date: date) -> list[dict]:
        return self.schedule_by_date.get(for_date, [])

    async def get_live_feed(self, game_id: int) -> Optional[dict]:
        self.live_feed_calls.append(game_id)
        return self.live_feed_by_id.get(game_id)


@pytest.fixture(autouse=True)
def _clear_mlb_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def _fixed_starting_balance(monkeypatch):
    monkeypatch.setattr(portfolio_service.settings, "paper_trading_starting_balance", 1000.0)


def _open_mlb_position(db_session, ticker: str) -> Market:
    market = Market(ticker=ticker, series_ticker="KXMLBGAME", title="Detroit vs Seattle Winner?", yes_price=0.55, no_price=0.45)
    db_session.add(market)
    db_session.commit()
    db_session.refresh(market)
    portfolio_service.buy(db_session, ticker, "YES", 10.0)
    return market


@pytest.mark.asyncio
async def test_poll_cycle_writes_one_snapshot_per_resolved_open_position(db_session):
    schedule = _load("mlb_schedule_20260806.json")
    live_feed = _load("mlb_live_824802.json")
    live_feed["gamePk"] = 823105  # DET @ SEA gamePk from the schedule fixture

    provider = StubProvider(
        schedule_by_date={date(2026, 8, 6): schedule},
        live_feed_by_id={823105: live_feed},
    )
    market = _open_mlb_position(db_session, "KXMLBGAME-26AUG061610DETSEA-DET")

    await run_mlb_poll_cycle(db_session, provider)

    snapshots = db_session.query(MLBGameStateSnapshot).all()
    assert len(snapshots) == 1
    snap = snapshots[0]
    assert snap.mlb_game_id == 823105
    assert snap.market_id == market.id
    assert snap.kalshi_yes_price == 0.55
    assert snap.kalshi_no_price == 0.45
    assert snap.runner_on_third is True
    assert snap.inning == 8

    # Cache now has this game's state, keyed by mlb_game_id.
    assert cache.get_state(823105) is not None
    assert provider.live_feed_calls == [823105]


@pytest.mark.asyncio
async def test_poll_cycle_skips_games_not_yet_due(db_session):
    schedule = _load("mlb_schedule_20260806.json")
    live_feed = _load("mlb_live_824802.json")
    live_feed["gamePk"] = 823105
    provider = StubProvider(
        schedule_by_date={date(2026, 8, 6): schedule}, live_feed_by_id={823105: live_feed}
    )
    _open_mlb_position(db_session, "KXMLBGAME-26AUG061610DETSEA-DET")

    await run_mlb_poll_cycle(db_session, provider)
    assert provider.live_feed_calls == [823105]

    # A second cycle immediately after should not re-fetch -- the live
    # interval (30s default) hasn't elapsed since the last poll.
    await run_mlb_poll_cycle(db_session, provider)
    assert provider.live_feed_calls == [823105]


@pytest.mark.asyncio
async def test_poll_cycle_stops_polling_final_games(db_session):
    schedule = _load("mlb_schedule_20260806.json")
    live_feed = _load("mlb_live_824802.json")
    live_feed["gamePk"] = 823105
    live_feed["gameData"]["status"] = {"abstractGameState": "Final", "detailedState": "Final"}
    provider = StubProvider(
        schedule_by_date={date(2026, 8, 6): schedule}, live_feed_by_id={823105: live_feed}
    )
    _open_mlb_position(db_session, "KXMLBGAME-26AUG061610DETSEA-DET")

    await run_mlb_poll_cycle(db_session, provider)
    assert provider.live_feed_calls == [823105]
    assert cache.get_state(823105).status == "final"

    # Force the cached last-polled time far enough in the past that a live
    # game would be due again -- a final game must still not be re-fetched.
    cache._last_polled_at[823105] = datetime.utcnow() - timedelta(hours=1)
    await run_mlb_poll_cycle(db_session, provider)
    assert provider.live_feed_calls == [823105]


@pytest.mark.asyncio
async def test_poll_cycle_no_open_mlb_positions_is_a_clean_noop(db_session):
    provider = StubProvider({}, {})
    market = Market(ticker="KXBTC-T50000", series_ticker="KXBTC", title="BTC threshold", yes_price=0.5, no_price=0.5)
    db_session.add(market)
    db_session.commit()
    portfolio_service.buy(db_session, "KXBTC-T50000", "YES", 10.0)

    await run_mlb_poll_cycle(db_session, provider)

    assert db_session.query(MLBGameStateSnapshot).count() == 0
    assert provider.live_feed_calls == []


@pytest.mark.asyncio
async def test_poll_cycle_handles_fetch_failure_gracefully(db_session):
    schedule = _load("mlb_schedule_20260806.json")
    provider = StubProvider(schedule_by_date={date(2026, 8, 6): schedule}, live_feed_by_id={})  # 404/None
    _open_mlb_position(db_session, "KXMLBGAME-26AUG061610DETSEA-DET")

    await run_mlb_poll_cycle(db_session, provider)  # must not raise

    assert db_session.query(MLBGameStateSnapshot).count() == 0
    assert cache.get_state(823105) is None
    assert cache.consecutive_errors(823105) == 1
