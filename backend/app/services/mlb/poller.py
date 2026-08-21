"""The testable core of MLB polling — one pass, called by
core/scheduler.py::run_mlb_polling_loop on a fixed tick. Only polls games
linked to markets with an open paper-trading position, at most once per
distinct game per cycle (two markets on the same game, e.g. both sides'
pick markets, share one fetch), and only as often as each game's own
adaptive interval calls for. A slow or failing MLB API can never stall
Kalshi ingestion or the exit-monitor loop — this is the only place in the
app that makes an MLB network call, and it never touches trade decisions.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.market import Market
from app.models.mlb_game_link import MLBGameLink
from app.models.mlb_game_state_snapshot import MLBGameStateSnapshot
from app.models.trade import Trade
from app.schemas.mlb import GameState
from app.services.mlb import cache, mapper, matcher
from app.services.mlb.provider import MLBProvider, default_provider

logger = logging.getLogger(__name__)

MLB_SERIES_TICKER = "KXMLBGAME"


def _interval_for_status(status: Optional[str]) -> Optional[float]:
    """None means "don't poll again" (game is final)."""
    if status == "live":
        return settings.mlb_poll_interval_live_seconds
    if status in ("delayed", "suspended"):
        return settings.mlb_poll_interval_delayed_seconds
    if status == "final":
        return None
    return settings.mlb_poll_interval_pregame_seconds  # scheduled, or unknown yet


def _is_due(game_id: int, cached: Optional[GameState], now: datetime) -> bool:
    if cached is not None and cached.status == "final":
        return False

    interval = _interval_for_status(cached.status if cached else None)
    if interval is None:
        return False

    if cache.consecutive_errors(game_id) >= settings.mlb_provider_max_consecutive_errors:
        interval = max(interval, settings.mlb_poll_interval_pregame_seconds)

    last_polled = cache.last_polled_at(game_id)
    if last_polled is None:
        return True
    return (now - last_polled).total_seconds() >= interval


async def _open_mlb_markets(db: Session) -> list[Market]:
    market_ids = (
        db.query(Trade.market_id)
        .join(Market, Trade.market_id == Market.id)
        .filter(Trade.exit_price.is_(None), Market.series_ticker == MLB_SERIES_TICKER)
        .distinct()
        .all()
    )
    ids = [row[0] for row in market_ids]
    if not ids:
        return []
    return db.query(Market).filter(Market.id.in_(ids)).all()


async def run_mlb_poll_cycle(db: Session, provider: MLBProvider = default_provider) -> None:
    now = datetime.utcnow()

    markets = await _open_mlb_markets(db)
    if not markets:
        return
    market_by_id = {m.id: m for m in markets}

    # Resolve (or reuse) each market's game link, then group by game id so
    # two markets on the same game share a single fetch this cycle.
    market_ids_by_game: dict[int, list[int]] = {}
    for market in markets:
        link = await matcher.resolve_market_game(db, market, provider)
        if link.mlb_game_id is not None:
            market_ids_by_game.setdefault(link.mlb_game_id, []).append(market.id)

    for game_id, market_ids in market_ids_by_game.items():
        cached = cache.get_state(game_id)
        if not _is_due(game_id, cached, now):
            continue

        raw = await provider.get_live_feed(game_id)
        if raw is None:
            cache.record_poll_failure(game_id, now)
            logger.info("MLB poll: failed to fetch live feed for game %s", game_id)
            continue

        try:
            state = mapper.map_live_feed(raw, fetched_at=now)
        except Exception:
            cache.record_poll_failure(game_id, now)
            logger.exception("MLB poll: failed to map live feed for game %s", game_id)
            continue

        cache.set_state(game_id, state)

        for market_id in market_ids:
            market = market_by_id.get(market_id)
            if market is None:
                continue
            db.add(
                MLBGameStateSnapshot(
                    mlb_game_id=game_id,
                    market_id=market_id,
                    fetched_at=now,
                    home_team=state.home_team,
                    away_team=state.away_team,
                    home_score=state.home_score,
                    away_score=state.away_score,
                    inning=state.inning,
                    inning_half=state.inning_half,
                    outs=state.outs,
                    runner_on_first=state.runner_on_first,
                    runner_on_second=state.runner_on_second,
                    runner_on_third=state.runner_on_third,
                    batting_team=state.batting_team,
                    fielding_team=state.fielding_team,
                    current_batter=state.current_batter,
                    current_pitcher=state.current_pitcher,
                    last_play_description=state.last_play_description,
                    status=state.status,
                    source_timestamp=state.source_timestamp,
                    data_age_seconds=state.data_age_seconds,
                    kalshi_yes_price=market.yes_price,
                    kalshi_no_price=market.no_price,
                )
            )
        db.commit()
