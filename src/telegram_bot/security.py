from functools import wraps
from typing import Callable, Set
from telegram import Update
from telegram.ext import ContextTypes
from src.common.logging import setup_logger
from src.config.settings import get_settings

logger = setup_logger("hermes.telegram.security")
settings = get_settings()


def get_allowed_user_ids() -> Set[int]:
    allowed = set()
    for uid in (settings.TELEGRAM_USER1_ID, settings.TELEGRAM_USER2_ID):
        if uid and str(uid).strip().isdigit():
            allowed.add(int(str(uid).strip()))
    return allowed


def is_user_allowed(user_id: int) -> bool:
    allowed = get_allowed_user_ids()
    if not allowed:
        return settings.ENVIRONMENT == "development"
    return user_id in allowed


def restricted(func: Callable) -> Callable:
    """Decorator ensuring that only authorized 2-person laboratory researchers can execute commands."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        if not is_user_allowed(user.id):
            logger.warning(f"Unauthorized Telegram access attempt by {user.username} (ID: {user.id})")
            if update.effective_message:
                await update.effective_message.reply_text(
                    "⛔ *Access Denied*\n\n"
                    "This Hermes Research Agent instance is strictly restricted to authorized laboratory researchers.\n\n"
                    f"Your Telegram User ID: `{user.id}`\n"
                    "Please add this ID to `TELEGRAM_USER1_ID` or `TELEGRAM_USER2_ID` in `.env` to authorize access.",
                    parse_mode="Markdown",
                )
            return

        return await func(update, context, *args, **kwargs)

    return wrapped
