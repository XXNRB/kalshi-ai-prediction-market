from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class BacktestTrade(BaseModel):
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    profit_loss: float
    exit_reason: str  # "exit_signal" | "end_of_window"


class StrategyResult(BaseModel):
    strategy: str  # "Signal-Based" | "Buy & Hold"
    starting_balance: float
    ending_balance: float
    total_return_pct: float
    win_rate_pct: Optional[float]
    max_drawdown_pct: float
    sharpe_ratio: float
    trade_count: int
    trades: List[BacktestTrade]


class BacktestResult(BaseModel):
    ticker: str
    period_start: datetime
    period_end: datetime
    candle_count: int
    signal_strategy: StrategyResult
    buy_hold_strategy: StrategyResult
