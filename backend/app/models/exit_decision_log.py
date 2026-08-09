from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExitDecisionLog(Base):
    """Audit trail: one row per exit-engine evaluation of an open trade,
    every monitor-loop cycle, whether or not it resulted in a sell. Lets
    the user see what Auto-Execute would have done (or did) at any point,
    and what Recommend Only was showing even if nobody was watching."""

    __tablename__ = "exit_decision_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"), index=True)
    ticker: Mapped[str] = mapped_column(String)
    side: Mapped[str] = mapped_column(String)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    mode: Mapped[str] = mapped_column(String)
    entry_price: Mapped[float] = mapped_column(Float)
    current_price: Mapped[float] = mapped_column(Float)
    peak_price: Mapped[float] = mapped_column(Float)
    contracts: Mapped[float] = mapped_column(Float)
    unrealized_profit_loss: Mapped[float] = mapped_column(Float)
    realized_profit_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    action: Mapped[str] = mapped_column(String)
    confidence: Mapped[int] = mapped_column(Integer)
    urgency: Mapped[str] = mapped_column(String)
    reason_codes: Mapped[List[str]] = mapped_column(JSON)
    summary: Mapped[str] = mapped_column(String)
    executed: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
