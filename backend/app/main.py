import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import allocation, analysis, backtest, exit_strategy, markets, portfolio
from app.config import settings
from app.core.scheduler import run_exit_monitor_loop, run_ingestion_loop
from app.database import init_db

stop_event = asyncio.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ingestion_task = asyncio.create_task(run_ingestion_loop(stop_event))
    exit_monitor_task = asyncio.create_task(run_exit_monitor_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await ingestion_task
        await exit_monitor_task


app = FastAPI(title="Kalshi AI Trading Research Assistant", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(markets.router)
app.include_router(analysis.router)
app.include_router(portfolio.router)
app.include_router(allocation.router)
app.include_router(exit_strategy.router)
app.include_router(backtest.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
