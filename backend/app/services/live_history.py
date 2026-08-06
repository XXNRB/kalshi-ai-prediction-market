import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from app.models.market import Market
from app.services.kalshi_client import KalshiClient, parse_candlestick

logger = logging.getLogger(__name__)

ONE_MINUTE = 1
ONE_HOUR = 60
ONE_DAY = 1440
MAX_LOOKBACK_SECONDS = 365 * 86400


def choose_period_interval(market_age_seconds: float) -> int:
    """Kalshi only accepts 1/60/1440-minute candles. Use the finest
    resolution that keeps the candle count reasonable for how long the
    market's been open."""
    if market_age_seconds <= 4 * 3600:
        return ONE_MINUTE
    if market_age_seconds <= 5 * 86400:
        return ONE_HOUR
    return ONE_DAY


async def fetch_live_history(
    market: Market, client: Optional[KalshiClient] = None
) -> Optional[list[dict[str, Any]]]:
    """Fetch real Kalshi candlestick history for a market, adaptively
    windowed so fast-moving recent markets get minute-level detail.
    Returns None (caller should fall back to local data) if the market has
    no known series_ticker or the live fetch fails for any reason."""
    if not market.series_ticker:
        return None

    # Prefer Kalshi's real market-open time over our own created_at (which
    # only reflects whenever *we* first ingested it) so already-open
    # markets get their real history, not just what we've observed so far.
    anchor = market.kalshi_open_time or market.created_at
    now = datetime.utcnow()
    market_age = (now - anchor).total_seconds()
    period_interval = choose_period_interval(market_age)

    lookback_seconds = min(max(market_age, 0), MAX_LOOKBACK_SECONDS)
    window_start = now - timedelta(seconds=lookback_seconds)

    # These are naive datetimes holding UTC wall-clock values (from
    # datetime.utcnow()) — .timestamp() on a naive datetime assumes
    # *local* time, silently shifting the epoch by the local UTC offset.
    # Tag them as UTC explicitly before converting.
    start_ts = int(window_start.replace(tzinfo=timezone.utc).timestamp())
    end_ts = int(now.replace(tzinfo=timezone.utc).timestamp())

    try:
        client = client or KalshiClient()
        raw_candles = await client.get_candlesticks(
            series_ticker=market.series_ticker,
            ticker=market.ticker,
            start_ts=start_ts,
            end_ts=end_ts,
            period_interval=period_interval,
        )
        points = [parse_candlestick(c) for c in raw_candles]
        points.sort(key=lambda p: p["timestamp"])
        return points
    except Exception:
        logger.warning(
            "Live candlestick fetch failed for %s; falling back to local history", market.ticker,
            exc_info=True,
        )
        return None
