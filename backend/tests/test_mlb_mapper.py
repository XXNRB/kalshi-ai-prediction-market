import json
from datetime import datetime
from pathlib import Path

from app.services.mlb.mapper import map_live_feed

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_map_live_feed_real_game_with_runner_on_third():
    """Fixture is a trimmed but real capture of a live Yankees @ Orioles
    game (gamePk 824802) — Yankees batting, top 8th, 1 out, runner on
    third only (statsapi marks an occupied base by the *presence* of the
    key in linescore.offense, not a boolean, so bases-empty keys are
    simply absent)."""
    raw = _load("mlb_live_824802.json")
    fetched_at = datetime(2026, 8, 21, 1, 15, 0)

    state = map_live_feed(raw, fetched_at=fetched_at)

    assert state.game_id == 824802
    assert state.home_team == "Baltimore Orioles"
    assert state.away_team == "New York Yankees"
    assert state.home_score == 1
    assert state.away_score == 6
    assert state.inning == 8
    assert state.inning_half == "Top"
    assert state.outs == 1
    assert state.status == "live"

    assert state.runner_on_first is False
    assert state.runner_on_second is False
    assert state.runner_on_third is True

    assert state.batting_team == "New York Yankees"
    assert state.fielding_team == "Baltimore Orioles"
    assert state.current_batter == "George Lombard Jr."
    # defense.pitcher (actually on the mound), not offense.pitcher (a
    # different, informational field on the batting team's own pitcher).
    assert state.current_pitcher == "Albert Suárez"
    assert "triples" in state.last_play_description

    assert state.source_provider == "statsapi.mlb.com"
    assert state.source_timestamp == datetime(2026, 8, 21, 1, 13, 54)
    assert state.data_age_seconds == 66.0  # fetched_at - source_timestamp


def test_map_live_feed_bases_empty_and_pregame_status():
    raw = {
        "gamePk": 999001,
        "metaData": {"timeStamp": "20260601_180000"},
        "gameData": {
            "status": {"abstractGameState": "Preview", "detailedState": "Scheduled"},
            "teams": {
                "home": {"name": "Detroit Tigers"},
                "away": {"name": "Seattle Mariners"},
            },
        },
        "liveData": {
            "linescore": {"teams": {"home": {}, "away": {}}, "offense": {}, "defense": {}},
            "plays": {"allPlays": []},
        },
    }
    fetched_at = datetime(2026, 6, 1, 18, 0, 5)

    state = map_live_feed(raw, fetched_at=fetched_at)

    assert state.status == "scheduled"
    assert state.home_score == 0
    assert state.away_score == 0
    assert state.inning is None
    assert state.outs is None
    assert state.runner_on_first is False
    assert state.runner_on_second is False
    assert state.runner_on_third is False
    assert state.batting_team is None
    assert state.current_pitcher is None
    assert state.last_play_description is None


def test_map_live_feed_delayed_and_suspended_status():
    def _with_detailed_state(detailed: str) -> dict:
        return {
            "gamePk": 1,
            "metaData": {"timeStamp": "20260601_180000"},
            "gameData": {
                "status": {"abstractGameState": "Live", "detailedState": detailed},
                "teams": {"home": {"name": "H"}, "away": {"name": "A"}},
            },
            "liveData": {
                "linescore": {"teams": {"home": {}, "away": {}}, "offense": {}, "defense": {}},
                "plays": {"allPlays": []},
            },
        }

    assert map_live_feed(_with_detailed_state("Delayed Start"), datetime.utcnow()).status == "delayed"
    assert map_live_feed(_with_detailed_state("Suspended"), datetime.utcnow()).status == "suspended"
    assert map_live_feed(_with_detailed_state("In Progress"), datetime.utcnow()).status == "live"


def test_map_live_feed_final_status():
    raw = {
        "gamePk": 2,
        "metaData": {"timeStamp": "20260601_220000"},
        "gameData": {
            "status": {"abstractGameState": "Final", "detailedState": "Final"},
            "teams": {"home": {"name": "H"}, "away": {"name": "A"}},
        },
        "liveData": {
            "linescore": {
                "teams": {"home": {"runs": 4}, "away": {"runs": 2}},
                "offense": {},
                "defense": {},
            },
            "plays": {"allPlays": []},
        },
    }
    state = map_live_feed(raw, datetime.utcnow())
    assert state.status == "final"
    assert state.home_score == 4
    assert state.away_score == 2
