from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.analysis import _save_analysis
from app.database import get_db
from app.models.market import Market
from app.models.price_history import PriceHistory
from app.schemas.allocation import AllocationItem, AllocationRequest, AllocationResponse
from app.services.ai_analyst import AIAnalystError, allocate_batch, analyze_market

router = APIRouter(prefix="/api/portfolio", tags=["allocation"])


@router.post("/allocate", response_model=AllocationResponse)
async def allocate(body: AllocationRequest, db: Session = Depends(get_db)) -> AllocationResponse:
    """Analyze a batch of candidate markets and size stakes across them
    together: markets below the conviction threshold are skipped
    entirely, and the capital that would have gone to them flows to the
    stronger picks (see services.ai_analyst.allocate_batch). Runs
    analyze_market sequentially per ticker — this is a user-triggered
    batch action, not a hot path."""
    analyses = {}
    markets = {}
    errors: list[str] = []

    for ticker in body.tickers:
        market = db.query(Market).filter(Market.ticker == ticker).one_or_none()
        if market is None:
            errors.append(f"Market '{ticker}' not found")
            continue

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
            errors.append(f"{ticker}: {exc}")
            continue

        record = _save_analysis(db, market, result)
        analyses[ticker] = result.model_copy(update={"analyzed_at": record.analyzed_at})
        markets[ticker] = market

    allocations = allocate_batch(analyses)

    items = [
        AllocationItem(
            ticker=ticker,
            market_title=markets[ticker].title,
            analysis=analyses[ticker],
            raw_allocation_pct=allocations[ticker].raw_allocation_pct,
            final_allocation_pct=allocations[ticker].final_allocation_pct,
            skipped=allocations[ticker].skipped,
            skip_reason=allocations[ticker].skip_reason,
        )
        for ticker in analyses
    ]

    return AllocationResponse(items=items, errors=errors)
