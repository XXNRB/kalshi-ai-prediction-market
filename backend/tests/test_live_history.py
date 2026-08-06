import time
from datetime import datetime, timedelta

import pytest

from app.models.market import Market
from app.services.live_history import (
    ONE_DAY,
    ONE_HOUR,
    ONE_MINUTE,
    choose_period_interval,
    fetch_live_history,
)


def test_choose_period_interval_scales_with_market_age():
    assert choose_period_interval(60) == ONE_MINUTE
    assert choose_period_interval(3 * 3600) == ONE_MINUTE
    assert choose_period_interval(2 * 86400) == ONE_HOUR
    assert choose_period_interval(30 * 86400) == ONE_DAY


def make_market(series_ticker=None, created_minutes_ago: int = 30, kalshi_open_time=None) -> Market:
    return Market(
        id=1,
        ticker="BTC-70K",
        series_ticker=series_ticker,
        title="Test",
        yes_price=0.5,
        no_price=0.5,
        volume=100,
        open_interest=10,
        liquidity=0.0,
        created_at=datetime.utcnow() - timedelta(minutes=created_minutes_ago),
        kalshi_open_time=kalshi_open_time,
    )


@pytest.mark.asyncio
async def test_fetch_live_history_returns_none_without_series_ticker():
    market = make_market(series_ticker=None)
    assert await fetch_live_history(market) is None


class FakeClient:
    def __init__(self, candles=None, raises=False):
        self._candles = candles or []
        self._raises = raises
        self.last_call_kwargs = None

    async def get_candlesticks(self, **kwargs):
        self.last_call_kwargs = kwargs
        if self._raises:
            raise RuntimeError("kalshi is down")
        return self._candles


@pytest.mark.asyncio
async def test_fetch_live_history_uses_true_utc_epoch_regardless_of_local_timezone():
    # Regression test: naive datetime.timestamp() assumes *local* time, which
    # silently shifted start_ts/end_ts by the local UTC offset and made every
    # live candlestick request return an empty window (all requested times
    # landed in the future relative to true UTC "now" on any non-UTC machine).
    market = make_market(series_ticker="KXBTC", created_minutes_ago=30)
    client = FakeClient(candles=[])

    await fetch_live_history(market, client=client)

    real_now = time.time()
    assert client.last_call_kwargs is not None
    assert abs(client.last_call_kwargs["end_ts"] - real_now) < 5
    assert client.last_call_kwargs["start_ts"] < client.last_call_kwargs["end_ts"]


@pytest.mark.asyncio
async def test_fetch_live_history_anchors_on_true_kalshi_open_time():
    # A market our system just started observing but that's actually been
    # open on Kalshi for a year should still request a year-long window,
    # not just the few minutes since we first saw it.
    true_open = datetime.utcnow() - timedelta(days=400)
    market = make_market(series_ticker="KXOLD", created_minutes_ago=1, kalshi_open_time=true_open)
    client = FakeClient(candles=[])

    await fetch_live_history(market, client=client)

    lookback = client.last_call_kwargs["end_ts"] - client.last_call_kwargs["start_ts"]
    # capped at MAX_LOOKBACK_SECONDS (365 days), not the true 400-day age,
    # and definitely not just the ~1 minute since we first ingested it
    assert 360 * 86400 < lookback <= 365 * 86400
    assert client.last_call_kwargs["period_interval"] == ONE_DAY


@pytest.mark.asyncio
async def test_fetch_live_history_parses_candles():
    market = make_market(series_ticker="KXBTC")
    candles = [
        {"end_period_ts": int(datetime.utcnow().timestamp()) - 60, "yes_bid": {"close_dollars": "0.4000"}, "volume_fp": "5.00"},
        {"end_period_ts": int(datetime.utcnow().timestamp()), "yes_bid": {"close_dollars": "0.4500"}, "volume_fp": "6.00"},
    ]
    points = await fetch_live_history(market, client=FakeClient(candles=candles))

    assert points is not None
    assert len(points) == 2
    assert points[0]["yes_price"] == 0.40
    assert points[1]["yes_price"] == 0.45
    # sorted ascending by timestamp
    assert points[0]["timestamp"] <= points[1]["timestamp"]


@pytest.mark.asyncio
async def test_fetch_live_history_returns_none_on_failure():
    market = make_market(series_ticker="KXBTC")
    points = await fetch_live_history(market, client=FakeClient(raises=True))
    assert points is None
