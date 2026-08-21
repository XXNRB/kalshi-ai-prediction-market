from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel

GameStatus = Literal["scheduled", "live", "delayed", "suspended", "final"]


class GameState(BaseModel):
    """A snapshot of one MLB game's live state, mapped from
    statsapi.mlb.com's live-feed endpoint (services/mlb/mapper.py). Display
    and storage only — see services/mlb/README-equivalent notes in
    PROJECT_STATUS.md: nothing here is read by the exit engine or any
    buy/sell decision yet.

    `source_timestamp` is MLB's own as-of time for this state (their
    metaData.timeStamp); `fetched_at` is when our provider actually pulled
    it; `data_age_seconds` is the gap between them — logged for latency
    analysis, not because any exploitable latency is assumed to exist.
    """

    game_id: int
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    inning: Optional[int] = None
    inning_half: Optional[str] = None  # "Top" | "Bottom" | "Middle" | "End"
    outs: Optional[int] = None
    runner_on_first: bool = False
    runner_on_second: bool = False
    runner_on_third: bool = False
    batting_team: Optional[str] = None
    fielding_team: Optional[str] = None
    current_batter: Optional[str] = None
    current_pitcher: Optional[str] = None
    last_play_description: Optional[str] = None
    status: GameStatus
    source_timestamp: Optional[datetime] = None
    fetched_at: datetime
    data_age_seconds: Optional[float] = None
    source_provider: str = "statsapi.mlb.com"
