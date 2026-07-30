import pytest

from app.models.market import Market
from app.models.price_history import PriceHistory
from app.services.ingestion import ingest_markets


class FakeKalshiClient:
    def __init__(self, markets):
        self._markets = markets

    async def list_markets(self, limit: int = 50):
        return self._markets


RAW_MARKET = {
    "ticker": "BTC-70K",
    "title": "Will BTC exceed $70,000?",
    "category": "Crypto",
    "yes_bid": 42,
    "no_bid": 58,
    "volume": 1000,
    "open_interest": 500,
    "expiration_time": "2026-08-01T00:00:00Z",
}


@pytest.mark.asyncio
async def test_ingest_creates_market_and_price_history(db_session):
    client = FakeKalshiClient([RAW_MARKET])

    count = await ingest_markets(db_session, client=client)

    assert count == 1
    market = db_session.query(Market).filter(Market.ticker == "BTC-70K").one()
    assert market.yes_price == 0.42
    assert market.title == "Will BTC exceed $70,000?"

    history = db_session.query(PriceHistory).filter(PriceHistory.market_id == market.id).all()
    assert len(history) == 1
    assert history[0].yes_price == 0.42


@pytest.mark.asyncio
async def test_ingest_only_appends_history_when_price_changes(db_session):
    client = FakeKalshiClient([RAW_MARKET])
    await ingest_markets(db_session, client=client)
    await ingest_markets(db_session, client=client)  # same price again

    market = db_session.query(Market).filter(Market.ticker == "BTC-70K").one()
    history = db_session.query(PriceHistory).filter(PriceHistory.market_id == market.id).all()
    assert len(history) == 1  # no duplicate row for unchanged price

    moved = dict(RAW_MARKET, yes_bid=50, no_bid=50)
    client_moved = FakeKalshiClient([moved])
    await ingest_markets(db_session, client=client_moved)

    history = db_session.query(PriceHistory).filter(PriceHistory.market_id == market.id).all()
    assert len(history) == 2
