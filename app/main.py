import asyncio
import signal
import uvicorn
from app.config.db import run_migrations
from app.config.settings import settings
from app.services.fetch_cycle import FetchCycleService
from app.api.app import api
from app.utils.logger import get_logger

logger = get_logger(__name__)

_running = True


def _handle_shutdown(sig, frame) -> None:
    global _running
    logger.info("Received signal %s — shutting down gracefully...", sig)
    _running = False


async def _interruptible_sleep(seconds: int) -> None:
    for _ in range(seconds):
        if not _running:
            break
        await asyncio.sleep(1)


async def run_worker() -> None:
    cycle_service = FetchCycleService()

    logger.info(
        "Worker started — fetching every %ds",
        settings.fetch_interval_seconds,
    )

    try:
        while _running:
            try:
                await cycle_service.run()
            except Exception as exc:
                logger.error("Cycle error (will retry next interval): %s", exc)

            if _running:
                logger.info(
                    "Sleeping %ds until next cycle...",
                    settings.fetch_interval_seconds,
                )
                await _interruptible_sleep(settings.fetch_interval_seconds)
    finally:
        await cycle_service.close()
        logger.info("Worker stopped")


async def run_api() -> None:
    config = uvicorn.Config(
        app=api,
        host="0.0.0.0",
        port=8000,
        log_level="warning",  # uvicorn logs handled by our logger
    )
    server = uvicorn.Server(config)
    logger.info("API started on http://0.0.0.0:8000")
    await server.serve()


async def run_scheduler() -> None:
    signal.signal(signal.SIGINT, _handle_shutdown)
    signal.signal(signal.SIGTERM, _handle_shutdown)

    logger.info("Running database migrations...")
    run_migrations()

    # Run worker and API concurrently in the same event loop
    await asyncio.gather(
        run_worker(),
        run_api(),
    )


def main() -> None:
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()