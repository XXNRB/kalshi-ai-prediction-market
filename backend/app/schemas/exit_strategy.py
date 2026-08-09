from datetime import datetime
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel

ExitMode = Literal["recommend_only", "auto_execute"]


class ExitAction(str, Enum):
    HOLD = "HOLD"
    SELL_PARTIAL = "SELL_PARTIAL"
    SELL_ALL = "SELL_ALL"


class ExitUrgency(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ExitDecision(BaseModel):
    """Structured output of the exit engine (services/exit_engine.py).
    `sell_fraction` is only meaningful for SELL_PARTIAL — no strategy in
    this pass emits SELL_PARTIAL, since partial-position execution isn't
    built yet, but the shape exists for future strategies."""

    action: ExitAction
    confidence: int  # 0-100
    urgency: ExitUrgency
    reason_codes: List[str]
    summary: str
    sell_fraction: Optional[float] = None


class ExitSettingsOut(BaseModel):
    mode: ExitMode
    updated_at: datetime


class ExitSettingsUpdate(BaseModel):
    mode: ExitMode


class ExitDecisionLogOut(BaseModel):
    id: int
    trade_id: int
    ticker: str
    side: str
    timestamp: datetime
    mode: ExitMode
    entry_price: float
    current_price: float
    peak_price: float
    contracts: float
    unrealized_profit_loss: float
    realized_profit_loss: Optional[float]
    action: ExitAction
    confidence: int
    urgency: ExitUrgency
    reason_codes: List[str]
    summary: str
    executed: bool
    execution_price: Optional[float]
