import asyncio
import logging

from app.config import settings
from app.database import SessionLocal
from app.services.exit_engine import run_exit_cycle
from app.services.ingestion import ingest_markets

logger = logging.getLogger(__name__)


async def run_ingestion_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        db = SessionLocal()
        try:
            await ingest_markets(db)
        except Exception:
            logger.exception("Market ingestion cycle failed")
        finally:
            db.close()

        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=settings.ingestion_interval_seconds
            )
        except asyncio.TimeoutError:
            pass


async def run_exit_monitor_loop(stop_event: asyncio.Event) -> None:
    """Runs independently of any browser tab or frontend polling — as
    long as this backend process is up, Auto-Execute keeps evaluating and
    (if enabled) selling on its own cadence."""
    while not stop_event.is_set():
        db = SessionLocal()
        try:
            run_exit_cycle(db)
        except Exception:
            logger.exception("Exit monitor cycle failed")
        finally:
            db.close()

        try:
            await asyncio.wait_for(
                stop_event.wait(), timeout=settings.exit_monitor_interval_seconds
            )
        except asyncio.TimeoutError:
            pass
