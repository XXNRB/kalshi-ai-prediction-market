from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.market import Market
from app.models.price_history import PriceHistory
from app.schemas.backtest import BacktestResult
from app.services.backtest import DEFAULT_BET_SIZE, DEFAULT_STARTING_BALANCE, run_backtest
from app.services.live_history import fetch_live_history

router = APIRouter(prefix="/api/markets", tags=["backtest"])


class BacktestRequest(BaseModel):
    starting_balance: float = DEFAULT_STARTING_BALANCE
    bet_size: float = DEFAULT_BET_SIZE


@router.post("/{ticker}/backtest", response_model=BacktestResult)
async def backtest(
    ticker: str, body: Optional[BacktestRequest] = None, db: Session = Depends(get_db)
) -> BacktestResult:
    body = body or BacktestRequest()
    market = db.query(Market).filter(Market.ticker == ticker).one_or_none()
    if market is None:
        raise HTTPException(status_code=404, detail=f"Market '{ticker}' not found")

    candles = await fetch_live_history(market)
    if candles is None:
        rows = (
            db.execute(
                select(PriceHistory)
                .where(PriceHistory.market_id == market.id)
                .order_by(PriceHistory.timestamp.asc())
            )
            .scalars()
            .all()
        )
        candles = [
            {"timestamp": r.timestamp, "yes_price": r.yes_price, "no_price": r.no_price, "volume": r.volume}
            for r in rows
        ]

    try:
        return run_backtest(market, candles, body.starting_balance, body.bet_size)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
