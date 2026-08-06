from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.ranking import OpportunityScore
from app.services.signals import Signal


class MarketSort(str, Enum):
    volume = "volume"
    movers = "movers"
    expiration = "expiration"
    prob_change = "prob_change"
    opportunity = "opportunity"


class MarketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    title: str
    category: Optional[str]
    description: Optional[str]
    yes_price: float
    no_price: float
    volume: int
    open_interest: int
    liquidity: float
    expiration_date: Optional[datetime]
    updated_at: datetime
    price_change_24h: float = 0.0
    signal: Optional[Signal] = None
    opportunity: Optional[OpportunityScore] = None


class PricePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    yes_price: float
    no_price: float
    volume: int
