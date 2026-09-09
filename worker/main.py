import asyncio
import logging
from .processor import PersistentWorker

logging.basicConfig(level=logging.INFO)

async def main() -> None:
    await PersistentWorker().run_forever()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Hermes Pro worker stopped")
