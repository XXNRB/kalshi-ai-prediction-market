from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.market import Market
from app.models.market_analysis import MarketAnalysisRecord
from app.models.price_history import PriceHistory
from app.schemas.analysis import MarketAnalysis
from app.services.ai_analyst import AIAnalystError, analyze_market

router = APIRouter(prefix="/api/markets", tags=["analysis"])


def _save_analysis(db: Session, market: Market, result: MarketAnalysis) -> MarketAnalysisRecord:
    record = (
        db.query(MarketAnalysisRecord).filter(MarketAnalysisRecord.market_id == market.id).one_or_none()
    )
    if record is None:
        record = MarketAnalysisRecord(market_id=market.id)
        db.add(record)

    record.market_implied_probability = result.market_implied_probability
    record.ai_estimated_probability = result.ai_estimated_probability
    record.edge = result.edge
    record.reasoning = result.reasoning
    record.risks = result.risks
    record.confidence = result.confidence
    record.recommendation = result.recommendation
    record.suggested_allocation_pct = result.suggested_allocation_pct
    record.data_sources = result.data_sources
    record.analyzed_at = datetime.utcnow()
    db.commit()
    db.refresh(record)
    return record


def _record_to_analysis(market: Market, record: MarketAnalysisRecord) -> MarketAnalysis:
    return MarketAnalysis(
        market_ticker=market.ticker,
        market_implied_probability=record.market_implied_probability,
        ai_estimated_probability=record.ai_estimated_probability,
        edge=record.edge,
        reasoning=record.reasoning,
        risks=record.risks,
        confidence=record.confidence,
        recommendation=record.recommendation,
        suggested_allocation_pct=record.suggested_allocation_pct,
        data_sources=record.data_sources,
        analyzed_at=record.analyzed_at,
    )


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
        result = await analyze_market(market, list(history))
    except AIAnalystError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    record = _save_analysis(db, market, result)
    return result.model_copy(update={"analyzed_at": record.analyzed_at})


@router.get("/{ticker}/analysis", response_model=MarketAnalysis)
def get_cached_analysis(ticker: str, db: Session = Depends(get_db)) -> MarketAnalysis:
    market = db.query(Market).filter(Market.ticker == ticker).one_or_none()
    if market is None:
        raise HTTPException(status_code=404, detail=f"Market '{ticker}' not found")

    record = (
        db.query(MarketAnalysisRecord).filter(MarketAnalysisRecord.market_id == market.id).one_or_none()
    )
    if record is None:
        raise HTTPException(status_code=404, detail=f"No analysis on file for '{ticker}'")

    return _record_to_analysis(market, record)
