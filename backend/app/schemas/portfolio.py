from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from app.schemas.exit_strategy import ExitDecision

Side = Literal["YES", "NO"]


class BuyRequest(BaseModel):
    ticker: str
    position: Side
    amount: float = Field(gt=0)


class PositionMetrics(BaseModel):
    """Pure numbers for an open position — no decisions. `expected_value_pct`
    reuses whatever AI analysis is already cached for the market (if any);
    everything else is arithmetic on price data already being collected.
    `peak_price`/`peak_profit_loss` ratchet up monotonically since entry
    (never decrease), so a later exit strategy can recognize a retracement
    instead of only ever comparing the current price to entry. Deciding
    what to do with these numbers is the exit engine's job
    (services/exit_engine.py), not this schema's."""

    roi_pct: float
    probability_change_pts: float
    expected_value_pct: Optional[float]
    momentum_pts_per_step: float
    risk_score: float
    unrealized_profit_loss: float
    peak_price: float
    peak_profit_loss: float


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
    metrics: Optional[PositionMetrics] = None
    exit_decision: Optional[ExitDecision] = None


class PortfolioSummary(BaseModel):
    starting_balance: float
    cash_balance: float
    portfolio_value: float
    total_pl: float
    roi_pct: float
    win_rate_pct: Optional[float]
    open_positions: List[TradeOut]
    closed_trades: List[TradeOut]
