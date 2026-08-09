from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.exit_decision_log import ExitDecisionLog
from app.schemas.exit_strategy import ExitDecisionLogOut, ExitSettingsOut, ExitSettingsUpdate
from app.services.exit_engine import get_or_create_exit_settings, set_exit_mode

router = APIRouter(prefix="/api/portfolio", tags=["exit-strategy"])


@router.get("/exit-settings", response_model=ExitSettingsOut)
def get_exit_settings(db: Session = Depends(get_db)) -> ExitSettingsOut:
    row = get_or_create_exit_settings(db)
    return ExitSettingsOut(mode=row.mode, updated_at=row.updated_at)


@router.put("/exit-settings", response_model=ExitSettingsOut)
def update_exit_settings(body: ExitSettingsUpdate, db: Session = Depends(get_db)) -> ExitSettingsOut:
    row = set_exit_mode(db, body.mode)
    return ExitSettingsOut(mode=row.mode, updated_at=row.updated_at)


@router.get("/exit-log", response_model=list[ExitDecisionLogOut])
def get_exit_log(limit: int = Query(default=50, le=200), db: Session = Depends(get_db)) -> list[ExitDecisionLogOut]:
    rows = (
        db.query(ExitDecisionLog)
        .order_by(desc(ExitDecisionLog.timestamp))
        .limit(limit)
        .all()
    )
    return [ExitDecisionLogOut.model_validate(r, from_attributes=True) for r in rows]
