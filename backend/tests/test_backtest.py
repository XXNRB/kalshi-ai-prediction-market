from datetime import datetime, timedelta

import pytest

from app.models.market import Market
from app.services.backtest import run_backtest


def make_market(minutes_to_expiration: int = 10_000) -> Market:
    return Market(
        id=1,
        ticker="TEST",
        title="Test market",
        yes_price=0.5,
        no_price=0.5,
        volume=5000,
        open_interest=100,
        liquidity=0.0,
        expiration_date=datetime.utcnow() + timedelta(minutes=minutes_to_expiration),
    )


def make_candles(prices: list) -> list:
    base = datetime.utcnow() - timedelta(minutes=len(prices))
    return [
        {"timestamp": base + timedelta(minutes=i), "yes_price": p, "no_price": round(1 - p, 4), "volume": 10}
        for i, p in enumerate(prices)
    ]


def test_signal_strategy_can_lose_when_a_deeper_dip_follows_entry():
    # 25 flat candles at 0.60 (establishes the window), a drop to 0.28
    # (entry), then a much deeper dip to 0.05 that becomes the new window
    # low, then a rise to 0.22 -- a real signal-driven exit, but still
    # below the 0.28 entry price, so the strategy can genuinely lose.
    prices = [0.60] * 25 + [0.28] + [0.05] * 20 + [0.22]
    candles = make_candles(prices)
    market = make_market()

    result = run_backtest(market, candles, starting_balance=100.0, bet_size=10.0)

    signal_result = result.signal_strategy
    assert signal_result.trade_count == 1
    trade = signal_result.trades[0]
    assert trade.entry_price == 0.28
    assert trade.exit_price == 0.22
    assert trade.exit_reason == "exit_signal"

    expected_profit = (10.0 / 0.28) * 0.22 - 10.0
    assert trade.profit_loss == pytest.approx(expected_profit, rel=1e-3)
    assert trade.profit_loss < 0  # exited below entry -- a losing trade
    assert signal_result.win_rate_pct == 0.0


def test_signal_strategy_profitable_round_trip():
    # 25 flat at 0.60, drop to 0.15 (entry near the low), stay at 0.15 long
    # enough to become the window's low, then jump to 0.40 (a real
    # exit-signal-driven profit, not a mark-to-market close).
    prices = [0.50] * 25 + [0.15] + [0.15] * 19 + [0.40]
    candles = make_candles(prices)
    market = make_market()

    result = run_backtest(market, candles, starting_balance=100.0, bet_size=10.0)

    signal_result = result.signal_strategy
    assert signal_result.trade_count == 1
    trade = signal_result.trades[0]
    assert trade.entry_price == 0.15
    assert trade.exit_price == 0.40
    assert trade.exit_reason == "exit_signal"

    expected_profit = (10.0 / 0.15) * 0.40 - 10.0
    assert trade.profit_loss == pytest.approx(expected_profit, rel=1e-3)
    assert trade.profit_loss > 0
    assert signal_result.win_rate_pct == 100.0
    assert signal_result.total_return_pct == pytest.approx(expected_profit / 100.0 * 100, rel=1e-3)


def test_signal_strategy_never_fires_on_a_flat_market():
    candles = make_candles([0.40] * 30)
    market = make_market()

    result = run_backtest(market, candles, starting_balance=100.0, bet_size=10.0)

    signal_result = result.signal_strategy
    assert signal_result.trade_count == 0
    assert signal_result.win_rate_pct is None
    assert signal_result.total_return_pct == 0.0
    assert signal_result.max_drawdown_pct == 0.0
    assert signal_result.sharpe_ratio == 0.0


def test_buy_and_hold_matches_first_to_last_price_move():
    candles = make_candles([0.20] * 5 + [0.30, 0.35, 0.45, 0.50])
    market = make_market()

    result = run_backtest(market, candles, starting_balance=100.0, bet_size=10.0)

    bh = result.buy_hold_strategy
    assert bh.trade_count == 1
    trade = bh.trades[0]
    assert trade.entry_price == 0.20
    assert trade.exit_price == 0.50

    contracts = 10.0 / 0.20
    expected_ending = (100.0 - 10.0) + contracts * 0.50
    assert bh.ending_balance == pytest.approx(expected_ending, rel=1e-3)
    assert bh.total_return_pct == pytest.approx((expected_ending - 100.0) / 100.0 * 100, rel=1e-3)


def test_run_backtest_raises_on_insufficient_history():
    market = make_market()
    with pytest.raises(ValueError, match="Not enough"):
        run_backtest(market, make_candles([0.5]))
    with pytest.raises(ValueError, match="Not enough"):
        run_backtest(market, [])
