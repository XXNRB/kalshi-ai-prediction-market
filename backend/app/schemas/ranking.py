from typing import List

from pydantic import BaseModel


class ScoreComponent(BaseModel):
    label: str
    score: float
    max_score: float
    explanation: str


class OpportunityScore(BaseModel):
    total: float
    stars: int
    tier_label: str
    researched: bool
    components: List[ScoreComponent]
