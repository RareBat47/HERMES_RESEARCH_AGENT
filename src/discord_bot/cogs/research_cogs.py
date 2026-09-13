from typing import Literal, Optional
import discord
from discord import app_commands
from discord.ext import commands
import httpx
from src.common.logging import setup_logger
from src.config.settings import get_settings
from src.discord_bot.ui.embeds import (
    create_citation_verification_embed,
    create_reading_mode_embed,
    create_search_result_embed,
)
from src.discord_bot.ui.views import SearchPaginationView

logger = setup_logger("hermes.discord.cogs")
settings = get_settings()
API_BASE = "http://localhost:8000"


class ResearchCog(commands.Cog):
    """Slash command suite for collaborative academic literature research."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # --------------------------------------------------------------------------
    # /project
    # --------------------------------------------------------------------------
    @app_commands.command(name="project", description="Manage collaborative research projects and shared truth.")
    @app_commands.describe(
        action="Action to perform",
        name="Project name",
    )
    async def project(
        self,
        interaction: discord.Interaction,
        action: Literal["create", "truth", "list"],
        name: Optional[str] = "Default Project",
    ):
        await interaction.response.defer()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if action == "create":
                    res = await client.post(f"{API_BASE}/projects/create", params={"name": name})
                    if res.status_code == 200:
                        data = res.json()
                        await interaction.followup.send(f"✅ Initialized project **{data['name']}** (ID: `{data['id']}`).")
                    else:
                        await interaction.followup.send(f"❌ Failed to create project: {res.text}")
                elif action == "truth":
                    res = await client.get(f"{API_BASE}/projects/1/truth")
                    if res.status_code == 200:
                        truth = res.json()
                        decisions_str = "\n".join([f"- **{d['title']}**: {d['decision']}" for d in truth.get("decisions", [])]) or "No decisions logged yet."
                        tasks_str = "\n".join([f"- `[#{t['id']}]` {t['title']} ({t['status']})" for t in truth.get("active_tasks", [])]) or "No active tasks."

                        embed = discord.Embed(
                            title=f"🏛️ Shared Truth: {truth.get('project_name')}",
                            description=f"**Core Research Question:** {truth.get('research_question') or 'Not yet formally declared.'}",
                            color=0x2A9D8F,
                        )
                        embed.add_field(name="📜 Key Decisions & Consensus", value=decisions_str[:1000], inline=False)
                        embed.add_field(name="📋 Active Research Tasks", value=tasks_str[:1000], inline=False)
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("❌ Could not retrieve project truth.")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Error: {e}")

    # --------------------------------------------------------------------------
    # /search
    # --------------------------------------------------------------------------
    @app_commands.command(name="search", description="Search academic literature across arXiv, Semantic Scholar, and PubMed.")
    @app_commands.describe(
        query="Research query or keywords",
        source="Source repository",
        limit="Max papers to return",
    )
    async def search(
        self,
        interaction: discord.Interaction,
        query: str,
        source: Literal["all", "arxiv", "semanticscholar"] = "all",
        limit: int = 5,
    ):
        await interaction.response.defer()
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.get(
                    f"{API_BASE}/papers/search",
                    params={"query": query, "source": source, "limit": limit},
                )
                if res.status_code != 200:
                    await interaction.followup.send(f"❌ Literature search error: {res.text}")
                    return

                papers = res.json()
                if not papers:
                    await interaction.followup.send(f"🔍 No papers found matching: *{query}*")
                    return

                async def ingest_trigger(identifier: str):
                    async with httpx.AsyncClient(timeout=120.0) as c:
                        await c.post(f"{API_BASE}/papers/ingest", params={"identifier": identifier, "project_id": 1})

                first_embed = create_search_result_embed(papers[0], 1, len(papers))
                view = SearchPaginationView(papers, ingest_trigger)
                await interaction.followup.send(embed=first_embed, view=view)
        except Exception as e:
            await interaction.followup.send(f"⚠️ Search failed: {e}")

    # --------------------------------------------------------------------------
    # /add_paper
    # --------------------------------------------------------------------------
    @app_commands.command(name="add_paper", description="Directly ingest a paper by arXiv ID, DOI, URL, or PMID.")
    @app_commands.describe(identifier="e.g., 2301.00234, 10.1145/..., or PDF URL")
    async def add_paper(self, interaction: discord.Interaction, identifier: str):
        await interaction.response.defer()
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                res = await client.post(
                    f"{API_BASE}/papers/ingest",
                    params={"identifier": identifier, "project_id": 1},
                )
                if res.status_code == 200:
                    data = res.json()
                    embed = discord.Embed(
                        title="📥 Paper Ingested & Indexed",
                        description=f"**Title:** {data['title']}\n**Key:** `{data['bibtex_key']}`",
                        color=0x2A9D8F,
                    )
                    embed.add_field(name="TEI / Section Parsed", value="✅ True" if data["is_parsed"] else "⚠️ Fallback", inline=True)
                    embed.add_field(name="Qdrant Vectors", value="✅ Indexed" if data["is_indexed"] else "❌ Pending", inline=True)
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"❌ Ingestion failed: {res.text}")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Error during ingestion: {e}")

    # --------------------------------------------------------------------------
    # /summarize
    # --------------------------------------------------------------------------
    @app_commands.command(name="summarize", description="Display deep structured reading mode note for a paper.")
    @app_commands.describe(paper="BibTeX key of paper")
    async def summarize(self, interaction: discord.Interaction, paper: str):
        await interaction.response.defer()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(f"{API_BASE}/papers/{paper}/note", params={"project_id": 1})
                if res.status_code == 200:
                    note = res.json()
                    embed = create_reading_mode_embed(note)
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"❌ Structured note for `{paper}` not found.")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Error: {e}")

    # --------------------------------------------------------------------------
    # /verify
    # --------------------------------------------------------------------------
    @app_commands.command(name="verify", description="Critic Citation Verifier: verify if a paper passage supports a claim.")
    @app_commands.describe(claim="Scientific claim to check", paper="BibTeX key")
    async def verify(self, interaction: discord.Interaction, claim: str, paper: str):
        await interaction.response.defer()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    f"{API_BASE}/agent/verify-claim",
                    json={"claim": claim, "bibtex_key": paper, "project_id": 1},
                )
                if res.status_code == 200:
                    data = res.json()
                    embed = create_citation_verification_embed(data)
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"❌ Verification failed: {res.text}")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Verification error: {e}")

    # --------------------------------------------------------------------------
    # /scratchpad
    # --------------------------------------------------------------------------
    @app_commands.command(name="scratchpad", description="Private per-researcher scratchpad for ideas and draft notes.")
    @app_commands.describe(action="view, add, or clear", note="Text note to append")
    async def scratchpad(
        self,
        interaction: discord.Interaction,
        action: Literal["view", "add", "clear"],
        note: Optional[str] = None,
    ):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        username = interaction.user.display_name

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if action == "add" and note:
                    res = await client.post(
                        f"{API_BASE}/projects/user/{user_id}/scratchpad",
                        params={"username": username},
                        json={"note": note, "project_id": 1},
                    )
                    await interaction.followup.send(f"📝 Appended to your private scratchpad:\n> {note}", ephemeral=True)
                else:
                    await interaction.followup.send("📝 Scratchpad updated.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ Scratchpad error: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ResearchCog(bot))
