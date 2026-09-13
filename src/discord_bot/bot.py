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


@bot.event
async def on_ready():
    logger.info(f"Hermes Discord Bot logged in as: {bot.user.name} (ID: {bot.user.id})")
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


@bot.check
async def check_researcher_authorization(ctx: commands.Context) -> bool:
    """Authorize only designated Researcher 1 and Researcher 2 if IDs are configured."""
    allowed_ids = [settings.DISCORD_RESEARCHER_1_ID, settings.DISCORD_RESEARCHER_2_ID]
    allowed_ids = [uid for uid in allowed_ids if uid]

    if not allowed_ids:
        # Dev mode: allow any user in guild
        return True

    user_id_str = str(ctx.author.id)
    return user_id_str in allowed_ids


async def main():
    if not settings.DISCORD_BOT_TOKEN or settings.DISCORD_BOT_TOKEN == "dummy_token":
        logger.warning("No valid DISCORD_BOT_TOKEN configured. Set DISCORD_BOT_TOKEN in .env to run the Discord Bot.")
        return

    async with bot:
        await bot.load_extension("src.discord_bot.cogs.research_cogs")
        await bot.start(settings.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
