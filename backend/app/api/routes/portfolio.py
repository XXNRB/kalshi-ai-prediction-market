from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.portfolio import BuyRequest, PortfolioSummary, TradeOut
from app.services import portfolio as portfolio_service
from app.services.portfolio import NotFoundError, PortfolioError

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.get("", response_model=PortfolioSummary)
def get_portfolio(db: Session = Depends(get_db)) -> PortfolioSummary:
    return portfolio_service.get_summary(db)


@router.post("/trades", response_model=TradeOut)
def buy_position(body: BuyRequest, db: Session = Depends(get_db)) -> TradeOut:
    try:
        trade = portfolio_service.buy(db, body.ticker, body.position, body.amount)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PortfolioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return portfolio_service.to_trade_out(trade)


@router.post("/trades/{trade_id}/sell", response_model=TradeOut)
def sell_position(trade_id: int, db: Session = Depends(get_db)) -> TradeOut:
    try:
        trade = portfolio_service.sell(db, trade_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PortfolioError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return portfolio_service.to_trade_out(trade)
