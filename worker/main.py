"""Separate worker entrypoint; queue integration is intentionally deferred."""
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("hermes.worker")

async def run() -> None:
    logger.info("Hermes Pro worker started in development mode")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("Hermes Pro worker stopped")
