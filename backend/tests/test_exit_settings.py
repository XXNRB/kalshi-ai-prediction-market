import pytest
from pydantic import ValidationError

from app.schemas.exit_strategy import ExitSettingsUpdate
from app.services.exit_engine import get_or_create_exit_settings, set_exit_mode


def test_get_or_create_exit_settings_creates_default_row(db_session):
    row = get_or_create_exit_settings(db_session)

    assert row.mode == "recommend_only"

    # calling again returns the same row, not a second one
    again = get_or_create_exit_settings(db_session)
    assert again.id == row.id


def test_set_exit_mode_persists_and_is_reflected_on_next_get(db_session):
    set_exit_mode(db_session, "auto_execute")

    row = get_or_create_exit_settings(db_session)
    assert row.mode == "auto_execute"

    set_exit_mode(db_session, "recommend_only")
    row = get_or_create_exit_settings(db_session)
    assert row.mode == "recommend_only"


def test_exit_settings_update_rejects_invalid_mode():
    with pytest.raises(ValidationError):
        ExitSettingsUpdate(mode="bogus")
