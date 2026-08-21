from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.mlb_game_link import MLBGameLink
from app.models.trade import Trade
from app.schemas.portfolio import BuyRequest, PortfolioSummary, TradeOut
from app.services import portfolio as portfolio_service
from app.services.exit_engine import evaluate_exit
from app.services.mlb import cache as mlb_cache
from app.services.portfolio import NotFoundError, PortfolioError

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _attach_exit_decision(trade_out: TradeOut, trade: Trade) -> TradeOut:
    """Composed here at the route layer, not inside portfolio_service —
    keeps services/portfolio.py and services/exit_engine.py from needing
    to import each other."""
    if trade_out.metrics is None:
        return trade_out
    decision = evaluate_exit(trade, trade.market, trade_out.metrics)
    return trade_out.model_copy(update={"exit_decision": decision})


def _attach_mlb_game_state(trade_out: TradeOut, trade: Trade, db: Session) -> TradeOut:
    """Read-only display composition, same pattern as _attach_exit_decision
    above — reads whatever the background MLB polling loop has already
    cached, never triggers a fetch itself, and never feeds exit_decision."""
    link = db.query(MLBGameLink).filter(MLBGameLink.market_id == trade.market_id).one_or_none()
    if link is None or link.mlb_game_id is None:
        return trade_out
    state = mlb_cache.get_state(link.mlb_game_id)
    if state is None:
        return trade_out
    return trade_out.model_copy(update={"mlb_game_state": state})


@router.get("", response_model=PortfolioSummary)
def get_portfolio(db: Session = Depends(get_db)) -> PortfolioSummary:
    summary = portfolio_service.get_summary(db)
    if not summary.open_positions:
        return summary

    trades_by_id = {
        t.id: t
        for t in db.query(Trade).filter(Trade.id.in_([p.id for p in summary.open_positions])).all()
    }
    updated_positions = [
        _attach_mlb_game_state(_attach_exit_decision(pos, trades_by_id[pos.id]), trades_by_id[pos.id], db)
        if pos.id in trades_by_id
        else pos
        for pos in summary.open_positions
    ]
    return summary.model_copy(update={"open_positions": updated_positions})


@router.post("/trades", response_model=TradeOut)
def buy_position(body: BuyRequest, db: Session = Depends(get_db)) -> TradeOut:
    try:
        trade = portfolio_service.buy(db, body.ticker, body.position, body.amount)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PortfolioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    trade_out = portfolio_service.to_trade_out(trade, db)
    return _attach_mlb_game_state(_attach_exit_decision(trade_out, trade), trade, db)


@router.post("/trades/{trade_id}/sell", response_model=TradeOut)
def sell_position(trade_id: int, db: Session = Depends(get_db)) -> TradeOut:
    try:
        trade = portfolio_service.sell(db, trade_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PortfolioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return portfolio_service.to_trade_out(trade, db)
