from pydantic import BaseModel, Field


class MarketAnalysis(BaseModel):
    """Structured output from Agent 1 (Research Analyst). Every field the
    spec requires is mandatory so the UI can never silently drop reasoning,
    confidence, or risk context behind a bare recommendation."""

    market_ticker: str
    market_implied_probability: float
    ai_estimated_probability: float = Field(ge=0, le=1)
    edge: float
    reasoning: list[str]
    risks: list[str]
    confidence: int = Field(ge=1, le=10)
    recommendation: str
    suggested_allocation_pct: float = Field(ge=0, le=100)
    data_sources: list[str]
