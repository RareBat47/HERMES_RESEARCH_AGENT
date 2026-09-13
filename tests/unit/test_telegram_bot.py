import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, User, Message, CallbackQuery
from telegram.ext import ContextTypes
from src.telegram_bot.security import is_user_allowed, restricted


@pytest.mark.asyncio
async def test_telegram_security_allowlist():
    with patch("src.telegram_bot.security.settings") as mock_settings:
        mock_settings.TELEGRAM_USER1_ID = "123456789"
        mock_settings.TELEGRAM_USER2_ID = "987654321"
        mock_settings.ENVIRONMENT = "production"

        assert is_user_allowed(123456789) is True
        assert is_user_allowed(987654321) is True
        assert is_user_allowed(111222333) is False


@pytest.mark.asyncio
async def test_telegram_restricted_decorator_blocks_unauthorized():
    mock_func = AsyncMock()
    decorated_func = restricted(mock_func)

    # Unauthorized user
    unauth_user = MagicMock(spec=User)
    unauth_user.id = 999999999
    unauth_user.username = "unauthorized_user"

    mock_msg = MagicMock(spec=Message)
    mock_msg.reply_text = AsyncMock()

    mock_update = MagicMock(spec=Update)
    mock_update.effective_user = unauth_user
    mock_update.effective_message = mock_msg
    mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    with patch("src.telegram_bot.security.settings") as mock_settings:
        mock_settings.TELEGRAM_USER1_ID = "123456789"
        mock_settings.TELEGRAM_USER2_ID = "987654321"
        mock_settings.ENVIRONMENT = "production"

        await decorated_func(mock_update, mock_context)

        # The underlying handler should NOT be called
        mock_func.assert_not_called()
        # The reply_text should notify Access Denied
        mock_msg.reply_text.assert_called_once()
        args, kwargs = mock_msg.reply_text.call_args
        assert "Access Denied" in args[0]
        assert "999999999" in args[0]


@pytest.mark.asyncio
async def test_telegram_restricted_decorator_allows_authorized():
    mock_func = AsyncMock(return_value="executed")
    decorated_func = restricted(mock_func)

    # Authorized user
    auth_user = MagicMock(spec=User)
    auth_user.id = 123456789
    auth_user.username = "lead_researcher"

    mock_msg = MagicMock(spec=Message)
    mock_msg.reply_text = AsyncMock()

    mock_update = MagicMock(spec=Update)
    mock_update.effective_user = auth_user
    mock_update.effective_message = mock_msg
    mock_context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

    with patch("src.telegram_bot.security.settings") as mock_settings:
        mock_settings.TELEGRAM_USER1_ID = "123456789"
        mock_settings.TELEGRAM_USER2_ID = "987654321"
        mock_settings.ENVIRONMENT = "production"

        await decorated_func(mock_update, mock_context)

        # The underlying handler should be called
        mock_func.assert_called_once()
