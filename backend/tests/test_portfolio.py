import pytest

from app.models.market import Market
from app.services import portfolio as portfolio_service
from app.services.portfolio import NotFoundError, PortfolioError


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
