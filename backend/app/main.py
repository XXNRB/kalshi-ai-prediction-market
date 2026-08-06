import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import analysis, markets, portfolio
from app.config import settings
from app.core.scheduler import run_ingestion_loop
from app.database import init_db

stop_event = asyncio.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(run_ingestion_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await task


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


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
