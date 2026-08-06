from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.market import Market
from app.models.market_analysis import MarketAnalysisRecord
from app.models.price_history import PriceHistory
from app.models.trade import Trade
from app.schemas.portfolio import PortfolioSummary, PositionStats, Side, TradeOut
from app.services import ranking
from app.services.signals import get_recent_history

TAKE_PROFIT_THRESHOLD_PCT = 20.0
MOMENTUM_WINDOW = 5


class PortfolioError(RuntimeError):
    """Invalid operation: bad amount, insufficient funds, zero price, already closed."""


class NotFoundError(RuntimeError):
    """Referenced market or trade doesn't exist."""


def _contracts(trade: Trade) -> float:
    return trade.amount / trade.entry_price


def _current_price_for_trade(trade: Trade) -> float:
    return trade.market.yes_price if trade.position == "YES" else trade.market.no_price


def _momentum(trade: Trade, history: List[PriceHistory]) -> float:
    recent = history[-MOMENTUM_WINDOW:]
    prices = [p.yes_price if trade.position == "YES" else p.no_price for p in recent]
    if len(prices) < 2:
        return 0.0
    steps = [b - a for a, b in zip(prices, prices[1:])]
    return round((sum(steps) / len(steps)) * 100, 2)


def _expected_value_pct(trade: Trade, current_price: float, cached: Optional[MarketAnalysisRecord]) -> Optional[float]:
    if cached is None or current_price <= 0:
        return None
    implied_prob_of_win = (
        cached.ai_estimated_probability if trade.position == "YES" else 1 - cached.ai_estimated_probability
    )
    return round((implied_prob_of_win - current_price) / current_price * 100, 1)


def compute_position_stats(
    trade: Trade,
    market: Market,
    history: List[PriceHistory],
    cached: Optional[MarketAnalysisRecord],
) -> PositionStats:
    current_price = market.yes_price if trade.position == "YES" else market.no_price
    roi_pct = round((current_price - trade.entry_price) / trade.entry_price * 100, 1)
    probability_change_pts = round((current_price - trade.entry_price) * 100, 1)
    risk, _ = ranking.risk_score(market, history, cached)

    if roi_pct >= TAKE_PROFIT_THRESHOLD_PCT:
        action = "consider_profit"
        reason = (
            f"Up {roi_pct:.0f}% from your entry price — past the {TAKE_PROFIT_THRESHOLD_PCT:.0f}% mark "
            "where locking in the gain is worth considering."
        )
    else:
        action = "hold"
        if roi_pct > 0:
            movement = f"Up {roi_pct:.0f}%"
        elif roi_pct < 0:
            movement = f"Down {abs(roi_pct):.0f}%"
        else:
            movement = "Flat"
        reason = f"{movement} — below the {TAKE_PROFIT_THRESHOLD_PCT:.0f}% threshold where taking profit gets flagged."

    return PositionStats(
        roi_pct=roi_pct,
        probability_change_pts=probability_change_pts,
        expected_value_pct=_expected_value_pct(trade, current_price, cached),
        momentum_pts_per_step=_momentum(trade, history),
        risk_score=risk,
        action=action,
        reason=reason,
    )


def to_trade_out(trade: Trade, db: Optional[Session] = None) -> TradeOut:
    contracts = _contracts(trade)
    is_open = trade.exit_price is None
    current_price = _current_price_for_trade(trade) if is_open else None
    profit_loss = (contracts * current_price - trade.amount) if is_open else trade.profit_loss

    position_stats = None
    if is_open and db is not None:
        history = get_recent_history(db, trade.market)
        cached = (
            db.query(MarketAnalysisRecord)
            .filter(MarketAnalysisRecord.market_id == trade.market_id)
            .one_or_none()
        )
        position_stats = compute_position_stats(trade, trade.market, history, cached)

    return TradeOut(
        id=trade.id,
        ticker=trade.market.ticker,
        market_title=trade.market.title,
        position=trade.position,
        status="open" if is_open else "closed",
        entry_price=trade.entry_price,
        exit_price=trade.exit_price,
        amount=trade.amount,
        contracts=round(contracts, 4),
        current_price=round(current_price, 4) if current_price is not None else None,
        profit_loss=round(profit_loss, 4) if profit_loss is not None else None,
        timestamp=trade.timestamp,
        exit_timestamp=trade.exit_timestamp,
        position_stats=position_stats,
    )


def get_cash_balance(db: Session) -> float:
    trades = db.query(Trade).all()
    spent = sum(t.amount for t in trades)
    returned = sum(_contracts(t) * t.exit_price for t in trades if t.exit_price is not None)
    return settings.paper_trading_starting_balance - spent + returned


def buy(db: Session, ticker: str, position: Side, amount: float) -> Trade:
    market = db.query(Market).filter(Market.ticker == ticker).one_or_none()
    if market is None:
        raise NotFoundError(f"Market '{ticker}' not found")

    if amount <= 0:
        raise PortfolioError("Amount must be greater than zero.")

    entry_price = market.yes_price if position == "YES" else market.no_price
    if entry_price <= 0:
        raise PortfolioError(f"No market price available for {position} on {ticker} right now.")

    cash_balance = get_cash_balance(db)
    if amount > cash_balance:
        raise PortfolioError(
            f"Insufficient funds: ${amount:.2f} requested, ${cash_balance:.2f} available."
        )

    trade = Trade(market_id=market.id, entry_price=entry_price, position=position, amount=amount)
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade


def sell(db: Session, trade_id: int) -> Trade:
    trade = db.query(Trade).filter(Trade.id == trade_id).one_or_none()
    if trade is None:
        raise NotFoundError(f"Trade {trade_id} not found")
    if trade.exit_price is not None:
        raise PortfolioError(f"Trade {trade_id} is already closed.")

    exit_price = _current_price_for_trade(trade)
    contracts = _contracts(trade)
    trade.exit_price = exit_price
    trade.profit_loss = contracts * exit_price - trade.amount
    trade.exit_timestamp = datetime.utcnow()

    db.commit()
    db.refresh(trade)
    return trade


def get_summary(db: Session) -> PortfolioSummary:
    trades = db.query(Trade).order_by(Trade.timestamp.desc()).all()
    open_trades = [t for t in trades if t.exit_price is None]
    closed_trades = [t for t in trades if t.exit_price is not None]

    cash_balance = get_cash_balance(db)
    open_value = sum(_contracts(t) * _current_price_for_trade(t) for t in open_trades)
    portfolio_value = cash_balance + open_value
    total_pl = portfolio_value - settings.paper_trading_starting_balance
    roi_pct = (total_pl / settings.paper_trading_starting_balance) * 100

    wins = sum(1 for t in closed_trades if (t.profit_loss or 0) > 0)
    win_rate_pct: Optional[float] = (wins / len(closed_trades) * 100) if closed_trades else None

    return PortfolioSummary(
        starting_balance=settings.paper_trading_starting_balance,
        cash_balance=round(cash_balance, 2),
        portfolio_value=round(portfolio_value, 2),
        total_pl=round(total_pl, 2),
        roi_pct=round(roi_pct, 2),
        win_rate_pct=round(win_rate_pct, 2) if win_rate_pct is not None else None,
        open_positions=[to_trade_out(t, db) for t in open_trades],
        closed_trades=[to_trade_out(t) for t in closed_trades],
    )
