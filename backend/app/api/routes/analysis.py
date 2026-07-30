from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.market import Market
from app.models.price_history import PriceHistory
from app.schemas.analysis import MarketAnalysis
from app.services.ai_analyst import AIAnalystError, analyze_market

router = APIRouter(prefix="/api/markets", tags=["analysis"])


@router.post("/{ticker}/analyze", response_model=MarketAnalysis)
async def analyze(ticker: str, db: Session = Depends(get_db)) -> MarketAnalysis:
    market = db.query(Market).filter(Market.ticker == ticker).one_or_none()
    if market is None:
        raise HTTPException(status_code=404, detail=f"Market '{ticker}' not found")

    history = (
        db.execute(
            select(PriceHistory)
            .where(PriceHistory.market_id == market.id)
            .order_by(PriceHistory.timestamp.asc())
        )
        .scalars()
        .all()
    )

    try:
        return await analyze_market(market, list(history))
    except AIAnalystError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
