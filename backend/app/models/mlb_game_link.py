from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MLBGameLink(Base):
    """Resolves a Market to an MLB gamePk exactly once
    (services/mlb/matcher.py), then gets reused for every subsequent
    polling cycle — never re-matched from scratch. `mlb_game_id` stays
    NULL until resolved; `match_method` records how (or that it's still
    unresolved), and `last_attempt_at` throttles retries on markets that
    haven't matched yet."""

    __tablename__ = "mlb_game_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), unique=True, index=True)
    mlb_game_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    match_method: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    matched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
