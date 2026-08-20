from datetime import datetime, timedelta

import pytest

from app.models.exit_decision_log import ExitDecisionLog
from app.models.market import Market
from app.models.trade import Trade
from app.schemas.exit_strategy import ExitAction, ExitDecision, ExitUrgency
from app.services import exit_engine, portfolio as portfolio_service


@pytest.fixture(autouse=True)
def _fixed_starting_balance(monkeypatch):
    monkeypatch.setattr(portfolio_service.settings, "paper_trading_starting_balance", 1000.0)


def make_market(db_session, ticker="BTC-70K", yes_price=0.40, no_price=0.60):
    market = Market(ticker=ticker, title="Test market", yes_price=yes_price, no_price=no_price)
    db_session.add(market)
    db_session.commit()
    db_session.refresh(market)
    return market


def _force_sell_all(trade, market, metrics, now, game_context) -> ExitDecision:
    """Test-only strategy that forces a SELL_ALL recommendation, independent
    of _flat_roi_strategy's own logic. Used to exercise run_exit_cycle's
    generic auto-execute safety-check paths (confidence/size/staleness/cap/
    race), which _flat_roi_strategy itself never triggers anymore now that
    it only ever returns HOLD."""
    return ExitDecision(
        action=ExitAction.SELL_ALL,
        confidence=90,
        urgency=ExitUrgency.HIGH,
        reason_codes=["TEST_FORCED_SELL"],
        summary="Forced sell for test.",
    )


# ---- _flat_roi_strategy ----------------------------------------------------


def test_flat_roi_strategy_holds_below_threshold():
    trade = Trade(position="YES", entry_price=0.40, amount=10.0)
    market = Market(id=1, ticker="X", title="X", yes_price=0.44, no_price=0.56)
    metrics = portfolio_service.compute_position_metrics(trade, market, history=[], cached=None)

    decision = exit_engine.evaluate_exit(trade, market, metrics)

    assert decision.action == ExitAction.HOLD
    assert decision.sell_fraction is None


def test_flat_roi_strategy_holds_with_profit_milestone_above_threshold():
    trade = Trade(position="YES", entry_price=0.40, amount=10.0)
    market = Market(id=1, ticker="X", title="X", yes_price=0.60, no_price=0.40)  # +50% ROI
    metrics = portfolio_service.compute_position_metrics(trade, market, history=[], cached=None)

    decision = exit_engine.evaluate_exit(trade, market, metrics)

    # Crossing the ROI threshold is informational only — never a sell
    # recommendation, since a price move alone isn't evidence selling
    # beats holding.
    assert decision.action == ExitAction.HOLD
    assert decision.sell_fraction is None
    assert "PROFIT_MILESTONE_REACHED" in decision.reason_codes
    assert "milestone" in decision.summary.lower()


# ---- run_exit_cycle: recommend_only -----------------------------------------


def test_run_exit_cycle_recommend_only_logs_without_selling(db_session):
    market = make_market(db_session, yes_price=0.60)  # bought at 0.40 -> +50% ROI
    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 10.0)
    trade.entry_price = 0.40
    db_session.commit()

    exit_engine.run_exit_cycle(db_session)

    db_session.refresh(trade)
    assert trade.exit_price is None  # never sold

    logs = db_session.query(ExitDecisionLog).filter(ExitDecisionLog.trade_id == trade.id).all()
    assert len(logs) == 1
    assert logs[0].executed is False
    assert logs[0].action == ExitAction.HOLD.value
    assert logs[0].mode == "recommend_only"


def test_run_exit_cycle_never_auto_sells_on_profit_milestone(db_session):
    """Regression test: a flat ROI-threshold crossing used to be a SELL_ALL
    trigger and could be auto-executed; now it's HOLD + an informational
    reason code, so it must never be sold even in auto_execute mode."""
    exit_engine.set_exit_mode(db_session, "auto_execute")
    market = make_market(db_session, yes_price=0.60)  # +50% ROI
    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 10.0)
    trade.entry_price = 0.40
    db_session.commit()

    exit_engine.run_exit_cycle(db_session)

    db_session.refresh(trade)
    assert trade.exit_price is None

    log = db_session.query(ExitDecisionLog).filter(ExitDecisionLog.trade_id == trade.id).one()
    assert log.executed is False
    assert log.action == ExitAction.HOLD.value
    assert "PROFIT_MILESTONE_REACHED" in log.reason_codes


# ---- run_exit_cycle: auto_execute safety checks -----------------------------
#
# _flat_roi_strategy never emits SELL_ALL anymore, so these tests force a
# SELL_ALL recommendation via a test-only strategy to exercise
# run_exit_cycle's own auto-execute safety logic independent of any
# particular strategy's behavior.


def test_run_exit_cycle_auto_execute_sells_when_checks_pass(db_session, monkeypatch):
    monkeypatch.setattr(exit_engine, "_ACTIVE_STRATEGY", _force_sell_all)
    exit_engine.set_exit_mode(db_session, "auto_execute")
    market = make_market(db_session, yes_price=0.60)
    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 10.0)
    trade.entry_price = 0.40
    db_session.commit()

    exit_engine.run_exit_cycle(db_session)

    db_session.refresh(trade)
    assert trade.exit_price == pytest.approx(0.60)

    logs = db_session.query(ExitDecisionLog).filter(ExitDecisionLog.trade_id == trade.id).all()
    assert len(logs) == 1
    assert logs[0].executed is True
    assert logs[0].execution_price == pytest.approx(0.60)
    assert logs[0].realized_profit_loss is not None


def test_run_exit_cycle_skips_low_confidence(db_session, monkeypatch):
    def _low_confidence_sell_all(trade, market, metrics, now, game_context):
        decision = _force_sell_all(trade, market, metrics, now, game_context)
        decision.confidence = 50  # below the default min of 70
        return decision

    monkeypatch.setattr(exit_engine, "_ACTIVE_STRATEGY", _low_confidence_sell_all)
    exit_engine.set_exit_mode(db_session, "auto_execute")
    market = make_market(db_session, yes_price=0.48)
    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 10.0)
    trade.entry_price = 0.40
    db_session.commit()

    exit_engine.run_exit_cycle(db_session)

    db_session.refresh(trade)
    assert trade.exit_price is None
    log = db_session.query(ExitDecisionLog).filter(ExitDecisionLog.trade_id == trade.id).one()
    assert log.executed is False
    assert "AUTO_SKIP_LOW_CONFIDENCE" in log.reason_codes


def test_run_exit_cycle_skips_oversized_stake(db_session, monkeypatch):
    monkeypatch.setattr(exit_engine, "_ACTIVE_STRATEGY", _force_sell_all)
    monkeypatch.setattr(exit_engine.settings, "exit_max_auto_sell_amount", 100.0)
    exit_engine.set_exit_mode(db_session, "auto_execute")
    market = make_market(db_session, yes_price=0.60)
    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 150.0)  # stake exceeds the $100 cap
    trade.entry_price = 0.40
    db_session.commit()

    exit_engine.run_exit_cycle(db_session)

    db_session.refresh(trade)
    assert trade.exit_price is None
    log = db_session.query(ExitDecisionLog).filter(ExitDecisionLog.trade_id == trade.id).one()
    assert log.executed is False
    assert "AUTO_SKIP_SIZE_CAP" in log.reason_codes


def test_run_exit_cycle_skips_stale_data(db_session, monkeypatch):
    monkeypatch.setattr(exit_engine, "_ACTIVE_STRATEGY", _force_sell_all)
    monkeypatch.setattr(exit_engine.settings, "exit_max_data_staleness_seconds", 120)
    exit_engine.set_exit_mode(db_session, "auto_execute")
    market = make_market(db_session, yes_price=0.60)
    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 10.0)
    trade.entry_price = 0.40
    db_session.commit()

    market.updated_at = datetime.utcnow() - timedelta(seconds=300)
    db_session.commit()

    exit_engine.run_exit_cycle(db_session)

    db_session.refresh(trade)
    assert trade.exit_price is None
    log = db_session.query(ExitDecisionLog).filter(ExitDecisionLog.trade_id == trade.id).one()
    assert log.executed is False
    assert "AUTO_SKIP_STALE_DATA" in log.reason_codes


def test_run_exit_cycle_handles_already_closed_race_without_crashing(db_session, monkeypatch):
    monkeypatch.setattr(exit_engine, "_ACTIVE_STRATEGY", _force_sell_all)
    exit_engine.set_exit_mode(db_session, "auto_execute")
    market = make_market(db_session, yes_price=0.60)
    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 10.0)
    trade.entry_price = 0.40
    db_session.commit()

    def _raise_already_closed(db, trade_id):
        raise portfolio_service.PortfolioError(f"Trade {trade_id} is already closed.")

    monkeypatch.setattr(exit_engine.portfolio_service, "sell", _raise_already_closed)

    exit_engine.run_exit_cycle(db_session)  # must not raise

    log = db_session.query(ExitDecisionLog).filter(ExitDecisionLog.trade_id == trade.id).one()
    assert log.executed is False
    assert "AUTO_SKIP_ALREADY_CLOSED" in log.reason_codes


def test_run_exit_cycle_respects_per_cycle_sell_cap(db_session, monkeypatch):
    monkeypatch.setattr(exit_engine, "_ACTIVE_STRATEGY", _force_sell_all)
    monkeypatch.setattr(exit_engine.settings, "exit_auto_max_sells_per_cycle", 2)
    exit_engine.set_exit_mode(db_session, "auto_execute")

    trades = []
    for i in range(5):
        market = make_market(db_session, ticker=f"M{i}", yes_price=0.60)
        trade = portfolio_service.buy(db_session, f"M{i}", "YES", 10.0)
        trade.entry_price = 0.40
        db_session.commit()
        trades.append(trade)

    exit_engine.run_exit_cycle(db_session)

    for t in trades:
        db_session.refresh(t)
    sold = [t for t in trades if t.exit_price is not None]
    assert len(sold) == 2
