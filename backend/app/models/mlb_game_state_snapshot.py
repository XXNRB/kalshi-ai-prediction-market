from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MLBGameStateSnapshot(Base):
    """One row per successful poll of a linked game: the full GameState at
    that moment, side-by-side with the linked market's Kalshi prices at the
    same instant. This is the dataset the future backtesting question runs
    against ("when Kalshi YES was 43c with a 1-run 9th-inning lead, what
    actually happened?") — display/storage only, never read by the exit
    engine or any trade decision."""

    __tablename__ = "mlb_game_state_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mlb_game_id: Mapped[int] = mapped_column(Integer, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    home_team: Mapped[str] = mapped_column(String)
    away_team: Mapped[str] = mapped_column(String)
    home_score: Mapped[int] = mapped_column(Integer)
    away_score: Mapped[int] = mapped_column(Integer)
    inning: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    inning_half: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    outs: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    runner_on_first: Mapped[bool] = mapped_column(Boolean, default=False)
    runner_on_second: Mapped[bool] = mapped_column(Boolean, default=False)
    runner_on_third: Mapped[bool] = mapped_column(Boolean, default=False)
    batting_team: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fielding_team: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    current_batter: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    current_pitcher: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_play_description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String)
    source_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    data_age_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    kalshi_yes_price: Mapped[float] = mapped_column(Float)
    kalshi_no_price: Mapped[float] = mapped_column(Float)
