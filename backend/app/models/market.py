from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Market(Base):
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    ticker: Mapped[str] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(String)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    yes_price: Mapped[float] = mapped_column(Float, default=0.0)
    no_price: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    open_interest: Mapped[int] = mapped_column(Integer, default=0)
    liquidity: Mapped[float] = mapped_column(Float, default=0.0)
    expiration_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    price_history: Mapped[List["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="market", cascade="all, delete-orphan"
    )
    trades: Mapped[List["Trade"]] = relationship(
        "Trade", back_populates="market", cascade="all, delete-orphan"
    )


from app.models.price_history import PriceHistory  # noqa: E402
from app.models.trade import Trade  # noqa: E402
