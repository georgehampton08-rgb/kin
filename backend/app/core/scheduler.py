"""
APScheduler — In-Process Scheduler
====================================
Runs background jobs inside the FastAPI process.

Jobs:
  - mark_stale_devices: every 2 min, marks ONLINE devices as STALE
    if their last_heartbeat is older than 12 minutes.

Lifecycle:
  - Started in app lifespan (main.py)
  - Stopped on shutdown

Cloud Run note:
  Requires min-instances=1 so exactly one scheduler is always alive.
  Do NOT use min-instances=0 with this scheduler.
"""
import logging
from datetime import datetime, timezone, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from app.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

STALE_THRESHOLD_MINUTES = 12

scheduler = AsyncIOScheduler(timezone="UTC")


async def _mark_stale_devices() -> None:
    """Mark ONLINE devices as STALE if no heartbeat within threshold."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=STALE_THRESHOLD_MINUTES)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text("""
                UPDATE device_status
                SET status = 'STALE', updated_at = now()
                WHERE status = 'ONLINE'
                  AND last_heartbeat < :cutoff
                RETURNING device_id
            """),
            {"cutoff": cutoff},
        )
        stale_ids = [row[0] for row in result.fetchall()]
        await session.commit()

    if stale_ids:
        logger.warning(
            f"[Scheduler] Marked {len(stale_ids)} device(s) STALE: {stale_ids}"
        )
        from app.core.ws_manager import ws_manager
        # Notify connected dashboards
        for stale_id in stale_ids:
            await ws_manager.push_device_status(stale_id)

    # Also close any TRIP_OPEN / TRIP_PAUSED trips for stale devices
    if stale_ids:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    UPDATE trips
                    SET status = 'TRIP_CLOSED',
                        end_time = now()
                    WHERE device_id = ANY(:device_ids)
                      AND status IN ('TRIP_OPEN', 'TRIP_PAUSED')
                """),
                {"device_ids": stale_ids},
            )
            await session.commit()
        logger.info(
            f"[Scheduler] Force-closed open trips for stale devices: {stale_ids}"
        )


def start_scheduler() -> None:
    scheduler.add_job(
        _mark_stale_devices,
        trigger="interval",
        minutes=2,
        id="mark_stale_devices",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[Scheduler] APScheduler started — stale-device job every 2 min")


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
    logger.info("[Scheduler] APScheduler stopped")
