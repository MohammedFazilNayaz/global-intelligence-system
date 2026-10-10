"""
Standalone Background Worker Process for Ingestion Scheduler and Document Pipeline.
Enables running background tasks isolated from the FastAPI web server when decoupled
deployment is desired.
"""

import asyncio
import signal
import sys
from backend.app.services.scheduler_service import scheduler
from backend.app.utils.logger import setup_logger

logger = setup_logger("worker.standalone")


async def main():
    logger.info("Starting standalone IngestionScheduler & DocumentPipelineWorkerPool...")
    scheduler.start()

    stop_event = asyncio.Event()

    def _shutdown_handler(sig_name: str):
        logger.info(f"Received signal {sig_name}. Initiating graceful shutdown...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, lambda s=sig.name: _shutdown_handler(s))
        except NotImplementedError:
            # Fallback for Windows where loop.add_signal_handler is not implemented
            pass

    try:
        await stop_event.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        logger.info("Executing cooperative shutdown of scheduler and worker pool...")
        await scheduler.stop()
        logger.info("Standalone background worker shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
