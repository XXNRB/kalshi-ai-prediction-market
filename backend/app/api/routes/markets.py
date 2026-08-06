from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.market import Market
from app.models.market_analysis import MarketAnalysisRecord
from app.models.price_history import PriceHistory
from app.schemas.market import MarketOut, MarketSort, PricePoint
from app.schemas.ranking import OpportunityScore
from app.services.live_history import fetch_live_history
from app.services.ranking import compute_opportunity
from app.services.signals import Signal, compute_signal, get_recent_history

router = APIRouter(prefix="/api/markets", tags=["markets"])


def _price_change_24h(db: Session, market: Market) -> float:
    cutoff = datetime.utcnow() - timedelta(hours=24)
    oldest = (
        db.query(PriceHistory)
        .filter(PriceHistory.market_id == market.id, PriceHistory.timestamp >= cutoff)
        .order_by(PriceHistory.timestamp.asc())
        .first()
    )
    if not oldest:
        return 0.0
    return round(market.yes_price - oldest.yes_price, 4)


def _signal(market: Market, recent_history: list[PriceHistory]) -> Signal:
    return compute_signal(market, recent_history)


def _opportunity(db: Session, market: Market, recent_history: list[PriceHistory]) -> OpportunityScore:
    cached = (
        db.query(MarketAnalysisRecord).filter(MarketAnalysisRecord.market_id == market.id).one_or_none()
    )
    return compute_opportunity(market, recent_history, cached)


@router.get("", response_model=list[MarketOut])
def list_markets(
    sort_by: MarketSort = Query(default=MarketSort.volume),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
) -> list[MarketOut]:
    markets = db.query(Market).all()
    results = []
    for m in markets:
        recent_history = get_recent_history(db, m)
        results.append(
            MarketOut.model_validate(m, from_attributes=True).model_copy(
                update={
                    "price_change_24h": _price_change_24h(db, m),
                    "signal": _signal(m, recent_history),
                    "opportunity": _opportunity(db, m, recent_history),
                }
            )
        )

    if sort_by == MarketSort.volume:
        results.sort(key=lambda m: m.volume, reverse=True)
    elif sort_by == MarketSort.movers:
        results.sort(key=lambda m: abs(m.price_change_24h), reverse=True)
    elif sort_by == MarketSort.expiration:
        results.sort(key=lambda m: m.expiration_date or datetime.max)
    elif sort_by == MarketSort.prob_change:
        results.sort(key=lambda m: abs(m.price_change_24h), reverse=True)
    elif sort_by == MarketSort.opportunity:
        results.sort(key=lambda m: m.opportunity.total if m.opportunity else 0, reverse=True)

    return results[:limit]


@router.get("/{ticker}", response_model=MarketOut)
def get_market(ticker: str, db: Session = Depends(get_db)) -> MarketOut:
    market = db.query(Market).filter(Market.ticker == ticker).one_or_none()
    if market is None:
        raise HTTPException(status_code=404, detail=f"Market '{ticker}' not found")
    out = MarketOut.model_validate(market, from_attributes=True)
    recent_history = get_recent_history(db, market)
    return out.model_copy(
        update={
            "price_change_24h": _price_change_24h(db, market),
            "signal": _signal(market, recent_history),
            "opportunity": _opportunity(db, market, recent_history),
        }
    )


@router.get("/{ticker}/history", response_model=list[PricePoint])
async def get_market_history(ticker: str, db: Session = Depends(get_db)) -> list[PricePoint]:
    market = db.query(Market).filter(Market.ticker == ticker).one_or_none()
    if market is None:
        raise HTTPException(status_code=404, detail=f"Market '{ticker}' not found")

    live_points = await fetch_live_history(market)
    if live_points is not None:
        return [PricePoint.model_validate(p) for p in live_points]

    rows = (
        db.execute(
            select(PriceHistory)
            .where(PriceHistory.market_id == market.id)
            .order_by(PriceHistory.timestamp.asc())
        )
        .scalars()
        .all()
    )
    return [PricePoint.model_validate(r, from_attributes=True) for r in rows]
