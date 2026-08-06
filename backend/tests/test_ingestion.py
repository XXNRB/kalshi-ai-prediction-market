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
    "series_ticker": "KXBTC",
    "title": "Will BTC exceed $70,000?",
    "category": "Crypto",
    "yes_bid_dollars": "0.4200",
    "no_bid_dollars": "0.5800",
    "volume_fp": "1000.00",
    "open_interest_fp": "500.00",
    "expiration_time": "2026-08-01T00:00:00Z",
    "open_time": "2025-08-28T20:45:00Z",
}


@pytest.mark.asyncio
async def test_ingest_creates_market_and_price_history(db_session):
    client = FakeKalshiClient([RAW_MARKET])

    count = await ingest_markets(db_session, client=client)

    assert count == 1
    market = db_session.query(Market).filter(Market.ticker == "BTC-70K").one()
    assert market.yes_price == 0.42
    assert market.title == "Will BTC exceed $70,000?"
    assert market.series_ticker == "KXBTC"
    assert market.kalshi_open_time is not None and market.kalshi_open_time.year == 2025

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

    moved = dict(RAW_MARKET, yes_bid_dollars="0.5000", no_bid_dollars="0.5000")
    client_moved = FakeKalshiClient([moved])
    await ingest_markets(db_session, client=client_moved)

    history = db_session.query(PriceHistory).filter(PriceHistory.market_id == market.id).all()
    assert len(history) == 2
