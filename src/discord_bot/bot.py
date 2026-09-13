import asyncio
import sys
import discord
from discord.ext import commands
from src.common.logging import setup_logger
from src.config.settings import get_settings

logger = setup_logger("hermes.discord.bot")
settings = get_settings()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


async def check_interaction_authorization(interaction: discord.Interaction) -> bool:
    """Enforces strict 2-researcher allowlist via USER1_ID and USER2_ID."""
    allowed = settings.allowed_discord_user_ids
    if not allowed:
        # Development mode: allow interaction if no allowlist configured
        return True

    user_id = str(interaction.user.id)
    if user_id in allowed:
        return True

    await interaction.response.send_message(
        "⛔ **Access Denied**: Your Discord user ID is not authorized for this laboratory.",
        ephemeral=True,
    )
    return False


bot.tree.interaction_check = check_interaction_authorization


@bot.event
async def on_ready():
    logger.info(f"Hermes Discord Bot logged in as: {bot.user.name} (ID: {bot.user.id})")
    allowed = settings.allowed_discord_user_ids
    logger.info(f"Enforcing 2-researcher allowlist: {allowed if allowed else 'Open/Development Mode'}")

    try:
        if settings.DISCORD_GUILD_ID:
            guild = discord.Object(id=int(settings.DISCORD_GUILD_ID))
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            logger.info(f"Synced {len(synced)} slash commands to target guild {settings.DISCORD_GUILD_ID}")
        else:
            synced = await bot.tree.sync()
            logger.info(f"Globally synced {len(synced)} slash commands.")
    except Exception as e:
        logger.error(f"Failed to sync slash commands: {e}")


async def main():
    if not settings.DISCORD_BOT_TOKEN or settings.DISCORD_BOT_TOKEN == "dummy_token":
        logger.warning("No valid DISCORD_BOT_TOKEN configured. Set DISCORD_BOT_TOKEN in .env to run the Discord Bot.")
        return

    async with bot:
        await bot.load_extension("src.discord_bot.cogs.research_cogs")
        await bot.start(settings.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
