from datetime import datetime, timedelta
from typing import List, Optional

from pydantic import BaseModel

from app.models.market import Market
from app.models.price_history import PriceHistory

RECENT_WINDOW = 20
NEAR_LOW_MARGIN = 0.03
NEAR_HIGH_MARGIN = 0.03
LOW_PRICE_CEILING = 0.30
MIN_RISE_OFF_LOW = 0.15
MIN_TIME_LEFT = timedelta(minutes=5)


class Signal(BaseModel):
    type: str  # "entry" | "exit" | "none"
    label: Optional[str] = None
    explanation: Optional[str] = None


NO_SIGNAL = Signal(type="none")


def compute_signal(
    market: Market, history: List[PriceHistory], as_of: Optional[datetime] = None
) -> Signal:
    """Deterministic, explainable entry/exit heuristic based on where the
    current price sits within its own recent range — not another AI call.

    This is market-level only: it can't know whether *you* hold a
    position, so the exit case is phrased conditionally rather than as
    personalized profit-taking advice. That needs the paper trading engine
    (tracking real entry prices), which doesn't exist yet.

    `as_of` lets the backtesting engine replay this signal against a past
    moment instead of real "now" — defaults to the live behavior.
    """
    if len(history) < 2 or market.volume <= 0:
        return NO_SIGNAL

    now = as_of or datetime.utcnow()
    if market.expiration_date is not None:
        time_left = market.expiration_date - now
        if time_left < MIN_TIME_LEFT:
            return NO_SIGNAL

    recent = history[-RECENT_WINDOW:]
    prices = [p.yes_price for p in recent]
    low, high = min(prices), max(prices)
    current = market.yes_price

    near_low = current <= low + NEAR_LOW_MARGIN and current <= LOW_PRICE_CEILING
    risen_off_low = current - low
    near_high = current >= high - NEAR_HIGH_MARGIN

    if near_high and risen_off_low >= MIN_RISE_OFF_LOW:
        return Signal(
            type="exit",
            label=f"Up sharply from its recent low ({low:.0%} → {current:.0%})",
            explanation=(
                f"YES has risen from a recent low of {low:.0%} to {current:.0%}. "
                "If you're holding a position from near that low, this could be a "
                "point to consider taking profit rather than assuming it keeps climbing."
            ),
        )

    if near_low and not near_high:
        return Signal(
            type="entry",
            label=f"Near its recent low ({current:.0%})",
            explanation=(
                f"YES is trading near its recent low of {low:.0%} with time still left "
                "before expiration. That doesn't mean it will go up — it's just cheap "
                "relative to where it's recently traded, which is worth a closer look, "
                "not a guarantee."
            ),
        )

    return NO_SIGNAL
