"""In-memory, single-process cache of the latest known state per MLB game,
plus the small bits of scheduling state the polling loop needs (last poll
time, consecutive-failure count) to implement adaptive, deduped polling
without hitting the database every tick.

Entries are always replaced wholesale, never mutated field-by-field — the
whole point is that a reader always sees either the old state or the new
one, never a half-updated mix, without needing a lock. That's safe here
specifically because this app's background loops are cooperative asyncio
tasks on one event loop, not real threads.
"""

from datetime import datetime
from typing import Optional

from app.schemas.mlb import GameState

_states: dict[int, GameState] = {}
_last_polled_at: dict[int, datetime] = {}
_consecutive_errors: dict[int, int] = {}


def get_state(mlb_game_id: int) -> Optional[GameState]:
    return _states.get(mlb_game_id)


def set_state(mlb_game_id: int, state: GameState) -> None:
    _states[mlb_game_id] = state
    _last_polled_at[mlb_game_id] = state.fetched_at
    _consecutive_errors[mlb_game_id] = 0


def record_poll_failure(mlb_game_id: int, at: datetime) -> int:
    _last_polled_at[mlb_game_id] = at
    _consecutive_errors[mlb_game_id] = _consecutive_errors.get(mlb_game_id, 0) + 1
    return _consecutive_errors[mlb_game_id]


def last_polled_at(mlb_game_id: int) -> Optional[datetime]:
    return _last_polled_at.get(mlb_game_id)


def consecutive_errors(mlb_game_id: int) -> int:
    return _consecutive_errors.get(mlb_game_id, 0)


def clear() -> None:
    """Test-only: reset all module-level state between test cases."""
    _states.clear()
    _last_polled_at.clear()
    _consecutive_errors.clear()
