import pytest

from app.models.market import Market
from app.models.market_analysis import MarketAnalysisRecord
from app.models.trade import Trade
from app.services import portfolio as portfolio_service
from app.services.portfolio import NotFoundError, PortfolioError, compute_position_stats


@pytest.fixture(autouse=True)
def _fixed_starting_balance(monkeypatch):
    # These tests' arithmetic assumes a $100 basis regardless of the app's
    # configured default — pin it so the suite stays correct either way.
    monkeypatch.setattr(portfolio_service.settings, "paper_trading_starting_balance", 100.0)


def make_market(db_session, ticker="BTC-70K", yes_price=0.40, no_price=0.60, title="Test market"):
    market = Market(ticker=ticker, title=title, yes_price=yes_price, no_price=no_price)
    db_session.add(market)
    db_session.commit()
    db_session.refresh(market)
    return market


def test_buy_creates_open_trade_and_deducts_cash(db_session):
    make_market(db_session, yes_price=0.40)

    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 20.0)

    assert trade.entry_price == 0.40
    assert trade.exit_price is None
    assert portfolio_service.get_cash_balance(db_session) == pytest.approx(80.0)


def test_buy_rejects_insufficient_funds(db_session):
    make_market(db_session, yes_price=0.40)
    with pytest.raises(PortfolioError, match="Insufficient funds"):
        portfolio_service.buy(db_session, "BTC-70K", "YES", 150.0)


def test_buy_rejects_zero_price_side(db_session):
    make_market(db_session, yes_price=0.0, no_price=1.0)
    with pytest.raises(PortfolioError, match="No market price available"):
        portfolio_service.buy(db_session, "BTC-70K", "YES", 10.0)


def test_buy_rejects_non_positive_amount(db_session):
    make_market(db_session)
    with pytest.raises(PortfolioError, match="greater than zero"):
        portfolio_service.buy(db_session, "BTC-70K", "YES", 0.0)


def test_buy_raises_not_found_for_unknown_ticker(db_session):
    with pytest.raises(NotFoundError):
        portfolio_service.buy(db_session, "NOPE", "YES", 10.0)


def test_sell_computes_profit_when_price_rises(db_session):
    market = make_market(db_session, yes_price=0.40)
    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 20.0)  # 50 contracts

    market.yes_price = 0.60
    db_session.commit()

    closed = portfolio_service.sell(db_session, trade.id)

    assert closed.exit_price == 0.60
    assert closed.profit_loss == pytest.approx(10.0)  # 50*0.60 - 20
    assert portfolio_service.get_cash_balance(db_session) == pytest.approx(110.0)  # 100-20+30


def test_sell_computes_loss_when_price_falls(db_session):
    market = make_market(db_session, yes_price=0.40)
    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 20.0)  # 50 contracts

    market.yes_price = 0.20
    db_session.commit()

    closed = portfolio_service.sell(db_session, trade.id)

    assert closed.profit_loss == pytest.approx(-10.0)  # 50*0.20 - 20
    assert portfolio_service.get_cash_balance(db_session) == pytest.approx(90.0)  # 100-20+10


def test_sell_rejects_already_closed(db_session):
    make_market(db_session, yes_price=0.40)
    trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 20.0)
    portfolio_service.sell(db_session, trade.id)

    with pytest.raises(PortfolioError, match="already closed"):
        portfolio_service.sell(db_session, trade.id)


def test_sell_raises_not_found_for_unknown_trade(db_session):
    with pytest.raises(NotFoundError):
        portfolio_service.sell(db_session, 999)


def test_get_summary_across_open_win_and_loss_trades(db_session):
    btc = make_market(db_session, ticker="BTC-70K", yes_price=0.40, title="BTC market")
    eth = make_market(db_session, ticker="ETH-5K", yes_price=0.50, title="ETH market")
    ai = make_market(db_session, ticker="AI-MODEL", yes_price=0.30, title="AI model market")

    win_trade = portfolio_service.buy(db_session, "BTC-70K", "YES", 20.0)  # 50 contracts @0.40
    loss_trade = portfolio_service.buy(db_session, "ETH-5K", "YES", 10.0)  # 20 contracts @0.50
    portfolio_service.buy(db_session, "AI-MODEL", "YES", 15.0)  # stays open, 50 contracts @0.30

    btc.yes_price = 0.60
    eth.yes_price = 0.30
    db_session.commit()
    portfolio_service.sell(db_session, win_trade.id)  # +10 profit
    portfolio_service.sell(db_session, loss_trade.id)  # -4 loss

    ai.yes_price = 0.45  # open position now worth more
    db_session.commit()

    summary = portfolio_service.get_summary(db_session)

    # cash: 100 - 20 - 10 - 15 (buys) + 30 (btc sell) + 6 (eth sell) = 91
    assert summary.cash_balance == pytest.approx(91.0)
    # open AI position now worth 50 contracts * 0.45 = 22.5
    assert summary.portfolio_value == pytest.approx(91.0 + 22.5)
    assert summary.total_pl == pytest.approx(91.0 + 22.5 - 100.0)
    assert summary.win_rate_pct == pytest.approx(50.0)  # 1 win, 1 loss
    assert len(summary.open_positions) == 1
    assert summary.open_positions[0].ticker == "AI-MODEL"
    assert summary.open_positions[0].profit_loss == pytest.approx(7.5)  # 22.5 - 15
    assert len(summary.closed_trades) == 2


def _build_market(yes_price: float, no_price: float) -> Market:
    return Market(id=1, ticker="BTC-70K", title="Test market", yes_price=yes_price, no_price=no_price)


def _build_analysis_record(ai_estimated_probability: float, confidence: int = 8) -> MarketAnalysisRecord:
    return MarketAnalysisRecord(
        market_id=1,
        market_implied_probability=0.50,
        ai_estimated_probability=ai_estimated_probability,
        edge=ai_estimated_probability - 0.50,
        reasoning=["reason"],
        risks=[],
        confidence=confidence,
        recommendation="Consider YES",
        suggested_allocation_pct=5.0,
        data_sources=["source"],
    )


def test_compute_position_stats_flags_take_profit_above_threshold():
    market = _build_market(yes_price=0.58, no_price=0.42)
    trade = Trade(position="YES", entry_price=0.34, amount=10.0)

    stats = compute_position_stats(trade, market, history=[], cached=None)

    assert stats.roi_pct == pytest.approx(70.6, abs=0.1)
    assert stats.action == "consider_profit"
    assert "20%" in stats.reason
    assert stats.expected_value_pct is None  # no cached analysis to reuse


def test_compute_position_stats_holds_below_threshold():
    market = _build_market(yes_price=0.63, no_price=0.37)
    trade = Trade(position="YES", entry_price=0.61, amount=10.0)

    stats = compute_position_stats(trade, market, history=[], cached=None)

    assert stats.roi_pct == pytest.approx(3.3, abs=0.1)
    assert stats.action == "hold"


def test_compute_position_stats_expected_value_uses_cached_analysis():
    market = _build_market(yes_price=0.50, no_price=0.50)
    trade = Trade(position="YES", entry_price=0.40, amount=10.0)
    cached = _build_analysis_record(ai_estimated_probability=0.65)

    stats = compute_position_stats(trade, market, history=[], cached=cached)

    # AI thinks YES is worth 0.65, current price is 0.50 -> +30% implied edge
    assert stats.expected_value_pct == pytest.approx(30.0, abs=0.1)


def test_compute_position_stats_no_side_uses_no_price_and_inverted_probability():
    market = _build_market(yes_price=0.30, no_price=0.70)
    trade = Trade(position="NO", entry_price=0.50, amount=10.0)  # bought NO when it was cheaper
    # AI thinks YES is unlikely (0.20) -> good news for the NO holder
    cached = _build_analysis_record(ai_estimated_probability=0.20)

    stats = compute_position_stats(trade, market, history=[], cached=cached)

    # NO side is up: entry 0.50 -> current no_price 0.70
    assert stats.roi_pct == pytest.approx(40.0, abs=0.1)
    # AI implies P(NO wins) = 1 - 0.20 = 0.80, vs current no_price 0.70 -> +14.3% edge
    assert stats.expected_value_pct == pytest.approx(14.3, abs=0.1)
