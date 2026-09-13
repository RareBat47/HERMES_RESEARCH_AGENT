import asyncio
from src.common.logging import setup_logger
from src.config.settings import get_settings

logger = setup_logger("hermes.bot.runner")
settings = get_settings()


def main() -> None:
    platform = settings.BOT_PLATFORM.lower().strip()
    if platform == "telegram":
        logger.info("Starting Telegram Bot interface...")
        from src.telegram_bot.bot import run_telegram_bot
        run_telegram_bot()
    else:
        logger.info("Starting Discord Bot interface...")
        from src.discord_bot.bot import main as run_discord_bot
        asyncio.run(run_discord_bot())


if __name__ == "__main__":
    main()
