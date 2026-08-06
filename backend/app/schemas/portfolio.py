from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Side = Literal["YES", "NO"]


class BuyRequest(BaseModel):
    ticker: str
    position: Side
    amount: float = Field(gt=0)


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


class PortfolioSummary(BaseModel):
    starting_balance: float
    cash_balance: float
    portfolio_value: float
    total_pl: float
    roi_pct: float
    win_rate_pct: Optional[float]
    open_positions: List[TradeOut]
    closed_trades: List[TradeOut]
