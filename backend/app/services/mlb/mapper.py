"""Pure functions: raw statsapi.mlb.com JSON -> our schemas. No I/O, no
state — easy to unit test against real captured fixtures (tests/fixtures/).
"""

from datetime import datetime
from typing import Any, Optional

from app.schemas.mlb import GameState

_STATUS_MAP = {
    "Preview": "scheduled",
    "Live": "live",
    "Final": "final",
}


def map_game_status(raw_status: dict[str, Any]) -> str:
    """MLB's abstractGameState is one of Preview/Live/Final; detailedState
    carries the finer distinction (e.g. "Delayed Start", "Suspended") we
    need for the adaptive polling interval."""
    abstract = raw_status.get("abstractGameState", "")
    detailed = (raw_status.get("detailedState") or "").lower()
    if abstract == "Live":
        if "suspended" in detailed:
            return "suspended"
        if "delayed" in detailed:
            return "delayed"
        return "live"
    return _STATUS_MAP.get(abstract, "scheduled")


def _parse_source_timestamp(raw: str) -> Optional[datetime]:
    """MLB's metaData.timeStamp, e.g. "20260821_011354" (UTC)."""
    try:
        return datetime.strptime(raw, "%Y%m%d_%H%M%S")
    except (ValueError, TypeError):
        return None


def _last_play_description(all_plays: list[dict[str, Any]]) -> Optional[str]:
    """The most recent *completed* play's description — the in-progress
    currentPlay usually has no description yet, so allPlays (searched from
    the end) is the reliable source."""
    for play in reversed(all_plays):
        if play.get("about", {}).get("isComplete"):
            desc = play.get("result", {}).get("description")
            if desc:
                return desc
    return None


def map_live_feed(raw: dict[str, Any], fetched_at: datetime) -> GameState:
    game_data = raw.get("gameData", {})
    live_data = raw.get("liveData", {})
    linescore = live_data.get("linescore", {})
    offense = linescore.get("offense", {})
    defense = linescore.get("defense", {})

    status = map_game_status(game_data.get("status", {}))

    source_timestamp = _parse_source_timestamp(raw.get("metaData", {}).get("timeStamp", ""))
    data_age_seconds = (
        (fetched_at - source_timestamp).total_seconds() if source_timestamp else None
    )

    home_team = game_data.get("teams", {}).get("home", {}).get("name", "")
    away_team = game_data.get("teams", {}).get("away", {}).get("name", "")

    return GameState(
        game_id=raw.get("gamePk"),
        home_team=home_team,
        away_team=away_team,
        home_score=linescore.get("teams", {}).get("home", {}).get("runs") or 0,
        away_score=linescore.get("teams", {}).get("away", {}).get("runs") or 0,
        inning=linescore.get("currentInning"),
        inning_half=linescore.get("inningState"),
        outs=linescore.get("outs"),
        # Presence of the key (not a boolean) is how statsapi marks an
        # occupied base — empty bases simply omit the key entirely.
        runner_on_first="first" in offense,
        runner_on_second="second" in offense,
        runner_on_third="third" in offense,
        batting_team=offense.get("team", {}).get("name"),
        fielding_team=defense.get("team", {}).get("name"),
        current_batter=offense.get("batter", {}).get("fullName"),
        # defense.pitcher is whoever's actually on the mound right now;
        # offense.pitcher is a different, informational field (the batting
        # team's own pitcher, not currently facing anyone) — not a fallback.
        current_pitcher=defense.get("pitcher", {}).get("fullName"),
        last_play_description=_last_play_description(live_data.get("plays", {}).get("allPlays", [])),
        status=status,
        source_timestamp=source_timestamp,
        fetched_at=fetched_at,
        data_age_seconds=data_age_seconds,
        source_provider="statsapi.mlb.com",
    )
