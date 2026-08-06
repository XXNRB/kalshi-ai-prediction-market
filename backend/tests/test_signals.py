from datetime import datetime, timedelta

from app.models.market import Market
from app.models.price_history import PriceHistory
from app.services.signals import compute_signal


def make_market(yes_price: float, volume: int = 1000, minutes_to_expiration: int = 60) -> Market:
    return Market(
        id=1,
        ticker="TEST",
        title="Test market",
        yes_price=yes_price,
        no_price=round(1 - yes_price, 4),
        volume=volume,
        open_interest=100,
        liquidity=0.0,
        expiration_date=datetime.utcnow() + timedelta(minutes=minutes_to_expiration),
    )


def make_history(prices: list) -> list:
    base = datetime.utcnow() - timedelta(minutes=len(prices))
    return [
        PriceHistory(
            market_id=1,
            timestamp=base + timedelta(minutes=i),
            yes_price=p,
            no_price=round(1 - p, 4),
            volume=100,
        )
        for i, p in enumerate(prices)
    ]


def test_entry_signal_when_near_recent_low():
    history = make_history([0.30, 0.25, 0.22, 0.20, 0.19])
    market = make_market(yes_price=0.19)

    signal = compute_signal(market, history)

    assert signal.type == "entry"
    assert "low" in signal.label.lower()


def test_exit_signal_when_risen_sharply_off_low():
    history = make_history([0.20, 0.25, 0.35, 0.45, 0.50])
    market = make_market(yes_price=0.50)

    signal = compute_signal(market, history)

    assert signal.type == "exit"
    assert "up sharply" in signal.label.lower()


def test_no_signal_in_middle_of_range():
    history = make_history([0.30, 0.40, 0.50, 0.45, 0.42])
    market = make_market(yes_price=0.42)

    signal = compute_signal(market, history)

    assert signal.type == "none"


def test_no_signal_with_insufficient_history():
    market = make_market(yes_price=0.20)
    assert compute_signal(market, []).type == "none"
    assert compute_signal(market, make_history([0.20])).type == "none"


def test_no_signal_with_no_volume():
    history = make_history([0.30, 0.25, 0.22, 0.20, 0.19])
    market = make_market(yes_price=0.19, volume=0)

    assert compute_signal(market, history).type == "none"


def test_no_signal_when_expiring_soon():
    history = make_history([0.30, 0.25, 0.22, 0.20, 0.19])
    market = make_market(yes_price=0.19, minutes_to_expiration=2)

    assert compute_signal(market, history).type == "none"


def test_no_signal_when_no_expiration_date_set():
    history = make_history([0.30, 0.25, 0.22, 0.20, 0.19])
    market = make_market(yes_price=0.19)
    market.expiration_date = None

    # still eligible on price grounds since expiration check only applies
    # when we actually know an expiration date
    signal = compute_signal(market, history)
    assert signal.type == "entry"
