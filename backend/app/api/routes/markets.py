from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.market import Market
from app.models.price_history import PriceHistory
from app.schemas.market import MarketOut, MarketSort, PricePoint
from app.services.live_history import fetch_live_history
from app.services.signals import Signal, compute_signal

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


def _signal(db: Session, market: Market) -> Signal:
    # most recent 50 rows, then re-sort ascending for compute_signal
    recent = (
        db.query(PriceHistory)
        .filter(PriceHistory.market_id == market.id)
        .order_by(PriceHistory.timestamp.desc())
        .limit(50)
        .all()
    )
    recent.reverse()
    return compute_signal(market, recent)


@router.get("", response_model=list[MarketOut])
def list_markets(
    sort_by: MarketSort = Query(default=MarketSort.volume),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db),
) -> list[MarketOut]:
    markets = db.query(Market).all()
    results = [
        MarketOut.model_validate(m, from_attributes=True).model_copy(
            update={"price_change_24h": _price_change_24h(db, m), "signal": _signal(db, m)}
        )
        for m in markets
    ]

    if sort_by == MarketSort.volume:
        results.sort(key=lambda m: m.volume, reverse=True)
    elif sort_by == MarketSort.movers:
        results.sort(key=lambda m: abs(m.price_change_24h), reverse=True)
    elif sort_by == MarketSort.expiration:
        results.sort(key=lambda m: m.expiration_date or datetime.max)
    elif sort_by == MarketSort.prob_change:
        results.sort(key=lambda m: abs(m.price_change_24h), reverse=True)

    return results[:limit]


@router.get("/{ticker}", response_model=MarketOut)
def get_market(ticker: str, db: Session = Depends(get_db)) -> MarketOut:
    market = db.query(Market).filter(Market.ticker == ticker).one_or_none()
    if market is None:
        raise HTTPException(status_code=404, detail=f"Market '{ticker}' not found")
    out = MarketOut.model_validate(market, from_attributes=True)
    return out.model_copy(
        update={"price_change_24h": _price_change_24h(db, market), "signal": _signal(db, market)}
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
