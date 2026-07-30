import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.market import Market
from app.models.price_history import PriceHistory
from app.services.kalshi_client import KalshiClient, cents_to_price, parse_expiration

logger = logging.getLogger(__name__)


async def ingest_markets(db: Session, client: Optional[KalshiClient] = None) -> int:
    """Fetch active markets from Kalshi, upsert into Market, and append a
    PriceHistory row whenever the price has moved. Returns the number of
    markets processed."""
    client = client or KalshiClient()
    raw_markets = await client.list_markets(limit=settings.ingestion_market_limit)

    for raw in raw_markets:
        ticker = raw.get("ticker")
        if not ticker:
            continue

        yes_price = cents_to_price(raw.get("yes_bid") or raw.get("last_price"))
        no_price = cents_to_price(raw.get("no_bid")) or round(1 - yes_price, 4)
        volume = raw.get("volume", 0) or 0
        open_interest = raw.get("open_interest", 0) or 0
        liquidity = cents_to_price(raw.get("liquidity"))

        market = db.query(Market).filter(Market.ticker == ticker).one_or_none()
        price_changed = market is None or market.yes_price != yes_price

        if market is None:
            market = Market(ticker=ticker)
            db.add(market)

        market.title = raw.get("title", ticker)
        market.category = raw.get("category")
        market.description = raw.get("subtitle") or raw.get("rules_primary")
        market.yes_price = yes_price
        market.no_price = no_price
        market.volume = volume
        market.open_interest = open_interest
        market.liquidity = liquidity
        market.expiration_date = parse_expiration(raw)

        db.flush()  # ensures market.id is populated for new rows

        if price_changed:
            db.add(
                PriceHistory(
                    market_id=market.id,
                    yes_price=yes_price,
                    no_price=no_price,
                    volume=volume,
                )
            )

    db.commit()
    logger.info("Ingested %d markets", len(raw_markets))
    return len(raw_markets)
