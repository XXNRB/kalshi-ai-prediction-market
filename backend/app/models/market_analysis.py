from datetime import datetime
from typing import List

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MarketAnalysisRecord(Base):
    """Cached result of the last AI analysis (Agent 1) run for a market.
    One row per market, overwritten on re-analysis. Powers the Probability
    Edge / Information Advantage / Risk components of the opportunity
    score (see app/services/ranking.py) and lets the market detail page
    show a prior result without spending a new AI call."""

    __tablename__ = "market_analyses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), unique=True, index=True)
    market_implied_probability: Mapped[float] = mapped_column(Float)
    ai_estimated_probability: Mapped[float] = mapped_column(Float)
    edge: Mapped[float] = mapped_column(Float)
    reasoning: Mapped[List[str]] = mapped_column(JSON)
    risks: Mapped[List[str]] = mapped_column(JSON)
    confidence: Mapped[int] = mapped_column(Integer)
    recommendation: Mapped[str] = mapped_column(String)
    suggested_allocation_pct: Mapped[float] = mapped_column(Float)
    data_sources: Mapped[List[str]] = mapped_column(JSON)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    market: Mapped["Market"] = relationship("Market")
