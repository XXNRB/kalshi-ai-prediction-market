import statistics
from typing import Any, Dict, List, Optional

from app.models.market import Market
from app.models.price_history import PriceHistory
from app.schemas.backtest import BacktestResult, BacktestTrade, StrategyResult
from app.services.signals import compute_signal

DEFAULT_STARTING_BALANCE = 100.0
DEFAULT_BET_SIZE = 10.0


def _to_history_points(candles: List[Dict[str, Any]]) -> List[PriceHistory]:
    return [
        PriceHistory(timestamp=c["timestamp"], yes_price=c["yes_price"], no_price=c["no_price"], volume=c["volume"])
        for c in candles
    ]


def _equity_curve_metrics(equity_curve: List[float]) -> tuple:
    """Returns (max_drawdown_pct, sharpe_ratio) from an equity curve.
    Sharpe here is unannualized -- mean/stdev of step-to-step % returns at
    whatever candle resolution this market's history came in (1-min, 1-hour,
    or 1-day), so it is NOT comparable across markets with different
    resolutions. Labeled as such wherever it's surfaced."""
    if len(equity_curve) < 2:
        return 0.0, 0.0

    peak = equity_curve[0]
    max_drawdown = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - value) / peak)

    step_returns = [
        (curr - prev) / prev for prev, curr in zip(equity_curve, equity_curve[1:]) if prev != 0
    ]
    if len(step_returns) < 2 or statistics.pstdev(step_returns) == 0:
        sharpe = 0.0
    else:
        sharpe = statistics.mean(step_returns) / statistics.pstdev(step_returns)

    return round(max_drawdown * 100, 2), round(sharpe, 3)


def _win_rate(trades: List[BacktestTrade]) -> Optional[float]:
    if not trades:
        return None
    wins = sum(1 for t in trades if t.profit_loss > 0)
    return round(wins / len(trades) * 100, 1)


def _strategy_result(
    strategy: str,
    starting_balance: float,
    ending_balance: float,
    trades: List[BacktestTrade],
    equity_curve: List[float],
) -> StrategyResult:
    max_drawdown_pct, sharpe = _equity_curve_metrics(equity_curve)
    return StrategyResult(
        strategy=strategy,
        starting_balance=starting_balance,
        ending_balance=round(ending_balance, 2),
        total_return_pct=round((ending_balance - starting_balance) / starting_balance * 100, 2),
        win_rate_pct=_win_rate(trades),
        max_drawdown_pct=max_drawdown_pct,
        sharpe_ratio=sharpe,
        trade_count=len(trades),
        trades=trades,
    )


def _simulate_signal_strategy(
    market: Market, candles: List[Dict[str, Any]], starting_balance: float, bet_size: float
) -> StrategyResult:
    """Walks the candles in order and follows services/signals.py's
    entry/exit heuristic exactly as a live user would have seen it at each
    point -- `compute_signal` is called with only the window *prior* to the
    current candle (never candle i itself) and an `as_of` matching that
    candle's real timestamp, so this can't cheat with hindsight."""
    history_points = _to_history_points(candles)
    cash = starting_balance
    contracts_held = 0.0
    entry_time = None
    entry_price = None
    trades: List[BacktestTrade] = []
    equity_curve: List[float] = []

    for i, candle in enumerate(candles):
        # Volume here is the market's real overall liquidity, not this one
        # candle's trickle (individual candles are often 0 even in an
        # active market) -- the gate in compute_signal means "is this
        # market liquid enough to trust," not "did a trade land in this
        # exact minute/day."
        synthetic_market = Market(
            ticker=market.ticker,
            title=market.title,
            yes_price=candle["yes_price"],
            no_price=candle["no_price"],
            volume=market.volume,
            expiration_date=market.expiration_date,
        )
        signal = compute_signal(synthetic_market, history_points[:i], as_of=candle["timestamp"])

        if contracts_held == 0 and signal.type == "entry" and candle["yes_price"] > 0:
            contracts_held = bet_size / candle["yes_price"]
            cash -= bet_size
            entry_time = candle["timestamp"]
            entry_price = candle["yes_price"]
        elif contracts_held > 0 and signal.type == "exit":
            proceeds = contracts_held * candle["yes_price"]
            cash += proceeds
            trades.append(
                BacktestTrade(
                    entry_time=entry_time,
                    entry_price=entry_price,
                    exit_time=candle["timestamp"],
                    exit_price=candle["yes_price"],
                    profit_loss=round(proceeds - bet_size, 4),
                    exit_reason="exit_signal",
                )
            )
            contracts_held = 0.0

        equity_curve.append(cash + contracts_held * candle["yes_price"])

    if contracts_held > 0:
        last = candles[-1]
        proceeds = contracts_held * last["yes_price"]
        cash += proceeds
        trades.append(
            BacktestTrade(
                entry_time=entry_time,
                entry_price=entry_price,
                exit_time=last["timestamp"],
                exit_price=last["yes_price"],
                profit_loss=round(proceeds - bet_size, 4),
                exit_reason="end_of_window",
            )
        )

    return _strategy_result("Signal-Based", starting_balance, cash, trades, equity_curve)


def _simulate_buy_and_hold(
    candles: List[Dict[str, Any]], starting_balance: float, bet_size: float
) -> StrategyResult:
    first, last = candles[0], candles[-1]
    contracts = bet_size / first["yes_price"] if first["yes_price"] > 0 else 0.0
    idle_cash = starting_balance - bet_size

    equity_curve = [idle_cash + contracts * c["yes_price"] for c in candles]
    ending_balance = idle_cash + contracts * last["yes_price"]

    trade = BacktestTrade(
        entry_time=first["timestamp"],
        entry_price=first["yes_price"],
        exit_time=last["timestamp"],
        exit_price=last["yes_price"],
        profit_loss=round(contracts * last["yes_price"] - bet_size, 4),
        exit_reason="end_of_window",
    )

    return _strategy_result("Buy & Hold", starting_balance, ending_balance, [trade], equity_curve)


def run_backtest(
    market: Market,
    candles: List[Dict[str, Any]],
    starting_balance: float = DEFAULT_STARTING_BALANCE,
    bet_size: float = DEFAULT_BET_SIZE,
) -> BacktestResult:
    if len(candles) < 2:
        raise ValueError("Not enough price history to backtest (need at least 2 data points).")

    return BacktestResult(
        ticker=market.ticker,
        period_start=candles[0]["timestamp"],
        period_end=candles[-1]["timestamp"],
        candle_count=len(candles),
        signal_strategy=_simulate_signal_strategy(market, candles, starting_balance, bet_size),
        buy_hold_strategy=_simulate_buy_and_hold(candles, starting_balance, bet_size),
    )
