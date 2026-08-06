from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Trade(Base):
    """Paper-trading trade record. Open position when exit_price is None,
    closed once sold (see app/services/portfolio.py)."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), index=True)
    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    position: Mapped[str] = mapped_column(String)  # "YES" or "NO"
    amount: Mapped[float] = mapped_column(Float)
    profit_loss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    exit_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    market: Mapped["Market"] = relationship("Market", back_populates="trades")
