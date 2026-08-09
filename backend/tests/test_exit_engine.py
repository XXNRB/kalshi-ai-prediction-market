from datetime import datetime, timedelta

import pytest

from app.models.exit_decision_log import ExitDecisionLog
from app.models.market import Market
from app.models.trade import Trade
from app.schemas.exit_strategy import ExitAction, ExitUrgency
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


# ---- _flat_roi_strategy ----------------------------------------------------


def test_flat_roi_strategy_holds_below_threshold():
    trade = Trade(position="YES", entry_price=0.40, amount=10.0)
    market = Market(id=1, ticker="X", title="X", yes_price=0.44, no_price=0.56)
    metrics = portfolio_service.compute_position_metrics(trade, market, history=[], cached=None)

    decision = exit_engine.evaluate_exit(trade, market, metrics)

    assert decision.action == ExitAction.HOLD
    assert decision.sell_fraction is None


def test_flat_roi_strategy_sells_all_above_threshold_with_urgency_scaling():
    trade = Trade(position="YES", entry_price=0.40, amount=10.0)
    market = Market(id=1, ticker="X", title="X", yes_price=0.60, no_price=0.40)  # +50% ROI
    metrics = portfolio_service.compute_position_metrics(trade, market, history=[], cached=None)

    decision = exit_engine.evaluate_exit(trade, market, metrics)

    assert decision.action == ExitAction.SELL_ALL
    assert decision.urgency == ExitUrgency.MEDIUM  # 30pt overshoot past the 20% threshold (15-40 band)
    assert decision.confidence >= 70
    assert "ROI_ABOVE_THRESHOLD" in decision.reason_codes


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
    assert logs[0].action == ExitAction.SELL_ALL.value
    assert logs[0].mode == "recommend_only"


# ---- run_exit_cycle: auto_execute -------------------------------------------


def test_run_exit_cycle_auto_execute_sells_when_checks_pass(db_session):
    exit_engine.set_exit_mode(db_session, "auto_execute")
    market = make_market(db_session, yes_price=0.60)
    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 10.0)
    trade.entry_price = 0.40  # +50% ROI -> confidence 90, well above the min
    db_session.commit()

    exit_engine.run_exit_cycle(db_session)

    db_session.refresh(trade)
    assert trade.exit_price == pytest.approx(0.60)

    logs = db_session.query(ExitDecisionLog).filter(ExitDecisionLog.trade_id == trade.id).all()
    assert len(logs) == 1
    assert logs[0].executed is True
    assert logs[0].execution_price == pytest.approx(0.60)
    assert logs[0].realized_profit_loss is not None


def test_run_exit_cycle_skips_low_confidence(db_session):
    exit_engine.set_exit_mode(db_session, "auto_execute")
    market = make_market(db_session, yes_price=0.48)  # bought at 0.40 -> +20% ROI exactly, confidence 60
    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 10.0)
    trade.entry_price = 0.40
    db_session.commit()

    exit_engine.run_exit_cycle(db_session)

    db_session.refresh(trade)
    assert trade.exit_price is None
    log = db_session.query(ExitDecisionLog).filter(ExitDecisionLog.trade_id == trade.id).one()
    assert log.executed is False


def test_run_exit_cycle_skips_oversized_stake(db_session, monkeypatch):
    monkeypatch.setattr(exit_engine.settings, "exit_max_auto_sell_amount", 100.0)
    exit_engine.set_exit_mode(db_session, "auto_execute")
    market = make_market(db_session, yes_price=0.60)  # +50% ROI, confidence 90 (would pass confidence check)
    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 150.0)  # stake exceeds the $100 cap
    trade.entry_price = 0.40
    db_session.commit()

    exit_engine.run_exit_cycle(db_session)

    db_session.refresh(trade)
    assert trade.exit_price is None
    log = db_session.query(ExitDecisionLog).filter(ExitDecisionLog.trade_id == trade.id).one()
    assert log.executed is False


def test_run_exit_cycle_skips_stale_data(db_session, monkeypatch):
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


def test_run_exit_cycle_handles_already_closed_race_without_crashing(db_session, monkeypatch):
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


def test_run_exit_cycle_respects_per_cycle_sell_cap(db_session, monkeypatch):
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
