from typing import List, Optional

from pydantic import BaseModel

from app.schemas.analysis import MarketAnalysis


class AllocationRequest(BaseModel):
    tickers: List[str]


class AllocationItem(BaseModel):
    ticker: str
    market_title: str
    analysis: MarketAnalysis
    raw_allocation_pct: float
    final_allocation_pct: float
    skipped: bool
    skip_reason: Optional[str] = None


class AllocationResponse(BaseModel):
    items: List[AllocationItem]
    errors: List[str] = []
