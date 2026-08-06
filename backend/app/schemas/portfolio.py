from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Side = Literal["YES", "NO"]


class BuyRequest(BaseModel):
    ticker: str
    position: Side
    amount: float = Field(gt=0)


class PositionStats(BaseModel):
    """Math-only stats for an open position — no trend detection, no AI
    call. `expected_value_pct` reuses whatever AI analysis is already
    cached for the market (if any); everything else is arithmetic on
    price data that's already being collected. `action` is a flat
    ROI-threshold flag, not a judgment about where the price is headed —
    the person decides, this just surfaces the number."""

    roi_pct: float
    probability_change_pts: float
    expected_value_pct: Optional[float]
    momentum_pts_per_step: float
    risk_score: float
    action: Literal["hold", "consider_profit"]
    reason: str


class TradeOut(BaseModel):
    id: int
    ticker: str
    market_title: str
    position: Side
    status: Literal["open", "closed"]
    entry_price: float
    exit_price: Optional[float]
    amount: float
    contracts: float
    current_price: Optional[float]  # live price for open positions
    profit_loss: Optional[float]  # realized (closed) or unrealized (open)
    timestamp: datetime
    exit_timestamp: Optional[datetime]
    position_stats: Optional[PositionStats] = None


class PortfolioSummary(BaseModel):
    starting_balance: float
    cash_balance: float
    portfolio_value: float
    total_pl: float
    roi_pct: float
    win_rate_pct: Optional[float]
    open_positions: List[TradeOut]
    closed_trades: List[TradeOut]
