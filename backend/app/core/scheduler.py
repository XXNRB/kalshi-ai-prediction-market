import asyncio
import logging

from app.config import settings
from app.database import SessionLocal
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
