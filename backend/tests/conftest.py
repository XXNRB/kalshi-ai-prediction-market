import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (  # noqa: F401
    exit_decision_log,
    exit_strategy,
    market,
    market_analysis,
    mlb_game_link,
    mlb_game_state_snapshot,
    price_history,
    trade,
)


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_local()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
