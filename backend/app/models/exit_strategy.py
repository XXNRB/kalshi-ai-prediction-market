from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExitStrategySetting(Base):
    """Single-row table holding the active exit mode. Lazily
    get-or-created (see services/exit_engine.py) so a fresh DB needs no
    seed step, matching how every other table here works without Alembic."""

    __tablename__ = "exit_strategy_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mode: Mapped[str] = mapped_column(String, default="recommend_only")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
