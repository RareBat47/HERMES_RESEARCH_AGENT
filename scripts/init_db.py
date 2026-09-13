import asyncio
from pathlib import Path
import sys

# Ensure repository root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.common.logging import setup_logger
from src.storage.database import init_db

logger = setup_logger("hermes.scripts.init_db")


async def main():
    logger.info("Initializing Hermes Research Agent database schema...")
    await init_db()
    logger.info("Database schema initialized successfully.")


if __name__ == "__main__":
    asyncio.run(main())
