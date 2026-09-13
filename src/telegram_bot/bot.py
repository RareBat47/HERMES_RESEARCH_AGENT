import asyncio
import sys
from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler
from src.common.logging import setup_logger
from src.config.settings import get_settings
from src.telegram_bot.handlers import (
    add_paper_command,
    ask_command,
    compare_command,
    draft_command,
    gaps_command,
    help_command,
    inline_button_callback,
    outline_command,
    scratchpad_command,
    search_command,
    start_command,
    summarize_command,
    tasks_command,
)

logger = setup_logger("hermes.telegram.bot")
settings = get_settings()


def run_telegram_bot() -> None:
    """Entrypoint for the Hermes 2-Researcher Telegram Bot."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or token in ("your_telegram_bot_token_here", "dummy_token"):
        logger.error(
            "TELEGRAM_BOT_TOKEN is not configured in .env!\n"
            "To get a bot token in 10 seconds:\n"
            "1. Open Telegram and message @BotFather\n"
            "2. Send /newbot, give it a name and username\n"
            "3. Paste the token into TELEGRAM_BOT_TOKEN in .env"
        )
        sys.exit(1)

    logger.info("Initializing Hermes Telegram Bot Application...")
    app = ApplicationBuilder().token(token).build()

    # Register research commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("add_paper", add_paper_command))
    app.add_handler(CommandHandler("ask", ask_command))
    app.add_handler(CommandHandler("gaps", gaps_command))
    app.add_handler(CommandHandler("summarize", summarize_command))
    app.add_handler(CommandHandler("compare", compare_command))
    app.add_handler(CommandHandler("outline", outline_command))
    app.add_handler(CommandHandler("draft", draft_command))
    app.add_handler(CommandHandler("tasks", tasks_command))
    app.add_handler(CommandHandler("scratchpad", scratchpad_command))

    # Register interactive inline button handler
    app.add_handler(CallbackQueryHandler(inline_button_callback))

    logger.info("Hermes Telegram Bot is active and listening for authorized research commands.")
    app.run_polling()


if __name__ == "__main__":
    run_telegram_bot()
