import logging
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.exit_decision_log import ExitDecisionLog
from app.models.exit_strategy import ExitStrategySetting
from app.models.market import Market
from app.models.market_analysis import MarketAnalysisRecord
from app.models.trade import Trade
from app.schemas.exit_strategy import ExitAction, ExitDecision, ExitMode, ExitUrgency
from app.schemas.portfolio import PositionMetrics
from app.services import portfolio as portfolio_service
from app.services.portfolio import PortfolioError
from app.services.signals import get_recent_history

logger = logging.getLogger(__name__)

FLAT_ROI_TAKE_PROFIT_THRESHOLD_PCT = 20.0

Strategy = Callable[[Trade, Market, PositionMetrics, Optional[datetime], Optional[dict]], ExitDecision]


def _flat_roi_strategy(
    trade: Trade,
    market: Market,
    metrics: PositionMetrics,
    now: Optional[datetime],
    game_context: Optional[dict],
) -> ExitDecision:
    """Starter/fallback strategy: a flat ROI threshold, nothing else —
    the same rule the app shipped with before this engine existed, now
    wrapped in the structured decision shape. Deliberately simple so
    Auto-Execute has a well-understood default while richer strategies
    (e.g. the upcoming MLB live-game-state one) are built on top of this
    same interface. Never emits SELL_PARTIAL — partial-position execution
    doesn't exist yet."""
    roi = metrics.roi_pct

    if roi < FLAT_ROI_TAKE_PROFIT_THRESHOLD_PCT:
        movement = "Up" if roi > 0 else "Down" if roi < 0 else "Flat"
        return ExitDecision(
            action=ExitAction.HOLD,
            confidence=80,
            urgency=ExitUrgency.LOW,
            reason_codes=["ROI_BELOW_THRESHOLD"],
            summary=(
                f"{movement} {abs(roi):.0f}% — below the "
                f"{FLAT_ROI_TAKE_PROFIT_THRESHOLD_PCT:.0f}% threshold."
            ),
        )

    overshoot = roi - FLAT_ROI_TAKE_PROFIT_THRESHOLD_PCT
    confidence = min(95, 60 + round(overshoot))
    if overshoot >= 40:
        urgency = ExitUrgency.HIGH
    elif overshoot >= 15:
        urgency = ExitUrgency.MEDIUM
    else:
        urgency = ExitUrgency.LOW

    return ExitDecision(
        action=ExitAction.SELL_ALL,
        confidence=confidence,
        urgency=urgency,
        reason_codes=["ROI_ABOVE_THRESHOLD"],
        summary=(
            f"Up {roi:.0f}% from entry — past the {FLAT_ROI_TAKE_PROFIT_THRESHOLD_PCT:.0f}% mark "
            "where locking in the gain is worth considering."
        ),
    )


# Swap point for future strategies (e.g. MLB live game-state) — replacing
# this one reference is the entire migration, no caller changes.
_ACTIVE_STRATEGY: Strategy = _flat_roi_strategy


def evaluate_exit(
    trade: Trade,
    market: Market,
    metrics: PositionMetrics,
    now: Optional[datetime] = None,
    game_context: Optional[dict] = None,
) -> ExitDecision:
    """Public entrypoint. `game_context` is reserved and unused this pass
    — a future strategy can read live game state from it without this
    signature, or any caller of it, needing to change."""
    return _ACTIVE_STRATEGY(trade, market, metrics, now, game_context)


def get_or_create_exit_settings(db: Session) -> ExitStrategySetting:
    row = db.query(ExitStrategySetting).first()
    if row is None:
        row = ExitStrategySetting(mode="recommend_only")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def set_exit_mode(db: Session, mode: ExitMode) -> ExitStrategySetting:
    row = get_or_create_exit_settings(db)
    row.mode = mode
    db.commit()
    db.refresh(row)
    return row


def _log_decision(
    db: Session,
    trade: Trade,
    market: Market,
    metrics: PositionMetrics,
    decision: ExitDecision,
    mode: str,
    executed: bool,
    execution_price: Optional[float] = None,
    realized_profit_loss: Optional[float] = None,
    skip_code: Optional[str] = None,
    skip_note: Optional[str] = None,
) -> None:
    """`skip_code`/`skip_note` capture *why* an otherwise sell-worthy
    decision wasn't executed (low confidence, oversized stake, stale
    data, per-cycle cap, mode) — distinct from the strategy's own
    reasoning (e.g. ROI_ABOVE_THRESHOLD), so the audit trail can answer
    both "what did the engine recommend" and "why didn't it act on it"."""
    current_price = market.yes_price if trade.position == "YES" else market.no_price
    reason_codes = list(decision.reason_codes)
    summary = decision.summary
    if skip_code is not None:
        reason_codes.append(skip_code)
        summary = f"{summary} ({skip_note})"

    db.add(
        ExitDecisionLog(
            trade_id=trade.id,
            ticker=market.ticker,
            side=trade.position,
            mode=mode,
            entry_price=trade.entry_price,
            current_price=current_price,
            peak_price=metrics.peak_price,
            contracts=trade.amount / trade.entry_price,
            unrealized_profit_loss=metrics.unrealized_profit_loss,
            realized_profit_loss=realized_profit_loss,
            action=decision.action.value,
            confidence=decision.confidence,
            urgency=decision.urgency.value,
            reason_codes=reason_codes,
            summary=summary,
            executed=executed,
            execution_price=execution_price,
        )
    )
    db.commit()


def _passes_auto_execute_safety_checks(
    trade: Trade, market: Market, decision: ExitDecision
) -> Optional[tuple[str, str]]:
    """Returns None if safe to auto-execute, else (code, human note)."""
    if decision.confidence < settings.exit_min_confidence_to_auto_execute:
        return (
            "AUTO_SKIP_LOW_CONFIDENCE",
            f"confidence {decision.confidence} below minimum {settings.exit_min_confidence_to_auto_execute}",
        )
    if trade.amount > settings.exit_max_auto_sell_amount:
        return (
            "AUTO_SKIP_SIZE_CAP",
            f"stake ${trade.amount:.2f} exceeds auto-sell size cap ${settings.exit_max_auto_sell_amount:.2f}",
        )
    staleness = (datetime.utcnow() - market.updated_at).total_seconds()
    if staleness > settings.exit_max_data_staleness_seconds:
        return (
            "AUTO_SKIP_STALE_DATA",
            f"market data is {staleness:.0f}s old, exceeds {settings.exit_max_data_staleness_seconds}s freshness window",
        )
    return None


def run_exit_cycle(db: Session) -> None:
    """One evaluation pass over every open position. Logs every
    evaluation regardless of outcome. In auto_execute mode, sells
    SELL_ALL-recommending positions that pass every safety check, up to
    exit_auto_max_sells_per_cycle — processed in a stable trade_id order
    so a single cap is applied predictably, not arbitrarily."""
    mode = get_or_create_exit_settings(db).mode
    now = datetime.utcnow()

    open_trades = (
        db.query(Trade).filter(Trade.exit_price.is_(None)).order_by(Trade.id.asc()).all()
    )

    sells_this_cycle = 0
    for trade in open_trades:
        try:
            market = trade.market
            history = get_recent_history(db, market)
            cached = (
                db.query(MarketAnalysisRecord)
                .filter(MarketAnalysisRecord.market_id == trade.market_id)
                .one_or_none()
            )
            metrics = portfolio_service.compute_position_metrics(trade, market, history, cached, db)
            decision = evaluate_exit(trade, market, metrics, now)

            if mode != "auto_execute" or decision.action != ExitAction.SELL_ALL:
                _log_decision(db, trade, market, metrics, decision, mode, executed=False)
                continue

            if sells_this_cycle >= settings.exit_auto_max_sells_per_cycle:
                note = f"per-cycle sell cap ({settings.exit_auto_max_sells_per_cycle}) reached"
                _log_decision(
                    db, trade, market, metrics, decision, mode, executed=False,
                    skip_code="AUTO_SKIP_CYCLE_CAP", skip_note=note,
                )
                logger.info("Exit cycle: per-cycle sell cap reached, flagging trade %s", trade.id)
                continue

            safety_skip = _passes_auto_execute_safety_checks(trade, market, decision)
            if safety_skip is not None:
                skip_code, skip_note = safety_skip
                _log_decision(
                    db, trade, market, metrics, decision, mode, executed=False,
                    skip_code=skip_code, skip_note=skip_note,
                )
                logger.info("Exit cycle: skipping auto-sell of trade %s: %s", trade.id, skip_note)
                continue

            try:
                closed = portfolio_service.sell(db, trade.id)
                sells_this_cycle += 1
                _log_decision(
                    db, trade, market, metrics, decision, mode,
                    executed=True, execution_price=closed.exit_price, realized_profit_loss=closed.profit_loss,
                )
            except PortfolioError:
                logger.info("Exit cycle: trade %s already closed, skipping", trade.id)
                _log_decision(
                    db, trade, market, metrics, decision, mode, executed=False,
                    skip_code="AUTO_SKIP_ALREADY_CLOSED",
                    skip_note="trade was already closed before this cycle could execute",
                )
        except Exception:
            logger.exception("Exit cycle: failed to evaluate trade %s", trade.id)
