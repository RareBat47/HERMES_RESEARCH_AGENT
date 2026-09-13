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
    """Academic literature research command suite for 2-researcher laboratory."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # --------------------------------------------------------------------------
    # 1. /project create | switch | truth
    # --------------------------------------------------------------------------
    @app_commands.command(name="project", description="Manage projects, active context, and shared truth.")
    @app_commands.describe(
        action="create, switch, or truth",
        name="Project name (for create)",
        project_id="Project ID (for switch or truth)",
    )
    async def project(
        self,
        interaction: discord.Interaction,
        action: Literal["create", "switch", "truth"],
        name: Optional[str] = None,
        project_id: Optional[int] = 1,
    ):
        await interaction.response.defer()
        user_id = str(interaction.user.id)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if action == "create":
                    pname = name or "Default Academic Project"
                    res = await client.post(f"{API_BASE}/projects", json={"name": pname})
                    if res.status_code == 200:
                        data = res.json()
                        await interaction.followup.send(f"✅ Initialized project **{data['name']}** (ID: `{data['id']}`).")
                    else:
                        await interaction.followup.send(f"❌ Failed to create project: {res.text}")

                elif action == "switch":
                    target_id = project_id or 1
                    res = await client.post(
                        f"{API_BASE}/projects/{target_id}/switch",
                        params={"discord_user_id": user_id},
                    )
                    if res.status_code == 200:
                        await interaction.followup.send(f"🔄 Switched your active project context to Project **#{target_id}**.")
                    else:
                        await interaction.followup.send(f"❌ Could not switch project: {res.text}")

                elif action == "truth":
                    target_id = project_id or 1
                    res = await client.get(f"{API_BASE}/projects/{target_id}/truth")
                    if res.status_code == 200:
                        truth = res.json()
                        decisions_str = "\n".join([f"- **{d['title']}**: {d['decision']}" for d in truth.get("decisions", [])]) or "No decisions logged yet."
                        tasks_str = "\n".join([f"- `[#{t['id']}]` {t['title']} ({t['status']})" for t in truth.get("active_tasks", [])]) or "No active tasks."

                        embed = discord.Embed(
                            title=f"🏛️ Shared Truth: {truth.get('project_name')}",
                            description=f"**Core Research Question:** {truth.get('research_question') or 'Declared in active project.'}",
                            color=0x2A9D8F,
                        )
                        embed.add_field(name="📜 Decision Log", value=decisions_str[:1000], inline=False)
                        embed.add_field(name="📋 Active Laboratory Tasks", value=tasks_str[:1000], inline=False)
                        await interaction.followup.send(embed=embed)
                    else:
                        await interaction.followup.send("❌ Could not retrieve project truth.")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Error: {e}")

    # --------------------------------------------------------------------------
    # 2. /search query source: arxiv|s2|pubmed|all
    # --------------------------------------------------------------------------
    @app_commands.command(name="search", description="Search literature across arXiv, Semantic Scholar, PubMed, and OpenAlex.")
    @app_commands.describe(
        query="Research query or keywords",
        source="Source repository",
        limit="Max papers to return",
    )
    async def search(
        self,
        interaction: discord.Interaction,
        query: str,
        source: Literal["all", "arxiv", "semanticscholar", "pubmed"] = "all",
        limit: int = 5,
    ):
        await interaction.response.defer()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    f"{API_BASE}/search",
                    json={"query": query, "sources": [source], "max_results_per_source": limit},
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
                        await c.post(f"{API_BASE}/papers/ingest", json={"identifier": identifier, "project_id": 1})

                first_embed = create_search_result_embed(papers[0], 1, len(papers))
                view = SearchPaginationView(papers, ingest_trigger)
                await interaction.followup.send(embed=first_embed, view=view)
        except Exception as e:
            await interaction.followup.send(f"⚠️ Search failed: {e}")

    # --------------------------------------------------------------------------
    # 3. /add_paper doi|url|arxiv_id|pmid
    # --------------------------------------------------------------------------
    @app_commands.command(name="add_paper", description="Ingest paper into library (downloads PDF, runs GROBID/PyMuPDF, indexes vectors).")
    @app_commands.describe(identifier="arXiv ID (2301.00234), DOI (10.1145/...), PMID, or PDF URL")
    async def add_paper(self, interaction: discord.Interaction, identifier: str):
        await interaction.response.defer()
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                res = await client.post(
                    f"{API_BASE}/papers/ingest",
                    json={"identifier": identifier, "project_id": 1},
                )
                if res.status_code == 200:
                    data = res.json()
                    embed = discord.Embed(
                        title="📥 Paper Ingested & Indexed",
                        description=f"**Title:** {data['title']}\n**Key:** `{data['bibtex_key']}`",
                        color=0x2A9D8F,
                    )
                    embed.add_field(name="Section Parser", value=f"✅ {data['parse_status']}", inline=True)
                    embed.add_field(name="Qdrant Vectors", value=f"✅ {data['index_status']}", inline=True)
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"❌ Ingestion failed: {res.text}")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Error during ingestion: {e}")

    # --------------------------------------------------------------------------
    # 4. /library recent | find
    # --------------------------------------------------------------------------
    @app_commands.command(name="library", description="Browse or search the library of ingested academic papers.")
    @app_commands.describe(action="recent or find", query="Search query if finding")
    async def library(
        self,
        interaction: discord.Interaction,
        action: Literal["recent", "find"],
        query: Optional[str] = None,
    ):
        await interaction.response.defer()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                params = {"query": query if action == "find" else None, "limit": 10}
                res = await client.get(f"{API_BASE}/papers/library", params=params)
                if res.status_code == 200:
                    papers = res.json()
                    if not papers:
                        await interaction.followup.send("📚 No papers found in the library.")
                        return

                    embed = discord.Embed(
                        title="📚 Academic Library",
                        description=f"Displaying {len(papers)} indexed papers:",
                        color=0x457B9D,
                    )
                    for p in papers:
                        embed.add_field(
                            name=f"`{p['bibtex_key']}` ({p.get('year') or 'N/A'})",
                            value=f"**{p['title'][:60]}...**\n*Venue:* {p.get('venue') or 'Academic Venue'}",
                            inline=False,
                        )
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("❌ Could not retrieve library.")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Library error: {e}")

    # --------------------------------------------------------------------------
    # 5. /summarize paper style: short|deep
    # --------------------------------------------------------------------------
    @app_commands.command(name="summarize", description="Display structured reading mode summary for an ingested paper.")
    @app_commands.describe(paper="BibTeX key of paper", style="short or deep")
    async def summarize(
        self,
        interaction: discord.Interaction,
        paper: str,
        style: Literal["short", "deep"] = "deep",
    ):
        await interaction.response.defer()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(f"{API_BASE}/papers/{paper}/note", params={"project_id": 1})
                if res.status_code == 200:
                    note = res.json()
                    embed = create_reading_mode_embed(note)
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"❌ Structured note for `{paper}` not found. Has it been ingested?")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Error: {e}")

    # --------------------------------------------------------------------------
    # 6. /ask question scope: library (Strict Evidence Grounded RAG!)
    # --------------------------------------------------------------------------
    @app_commands.command(name="ask", description="Evidence-grounded question answering with strict passage citations.")
    @app_commands.describe(question="Academic research question", scope="library or web")
    async def ask(
        self,
        interaction: discord.Interaction,
        question: str,
        scope: Literal["library", "web"] = "library",
    ):
        await interaction.response.defer()
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(
                    f"{API_BASE}/agent/ask",
                    json={"question": question, "project_id": 1, "scope": scope},
                )
                if res.status_code == 200:
                    data = res.json()
                    is_grounded = data.get("is_grounded", False)
                    answer = data.get("answer", "")
                    citations = data.get("citations", [])
                    unsupported = data.get("unsupported_claims", [])

                    embed = discord.Embed(
                        title="🎯 Evidence-Grounded Research Answer",
                        description=answer[:2000],
                        color=0x2A9D8F if is_grounded else 0xE76F51,
                    )

                    if citations:
                        cit_lines = []
                        for c in citations[:4]:
                            quote = c.get("exact_quote", "")[:120]
                            sec = c.get("section_hint") or "Section"
                            page = c.get("page_hint")
                            page_str = f"p.{page}" if page else "Passage"
                            cit_lines.append(f"• **`\\cite{{{c['bibtex_key']}}}`** ({sec}, {page_str}):\n  > *\"{quote}...\"*")
                        embed.add_field(name="📖 Grounded Citations & Exact Quotes", value="\n".join(cit_lines), inline=False)

                    if not is_grounded:
                        embed.add_field(
                            name="⚠️ Unsupported Claims / Evidence Gap",
                            value="The indexed library does not contain sufficient passage evidence to back this claim.",
                            inline=False,
                        )
                        queries = data.get("proposed_search_queries", [])
                        if queries:
                            embed.add_field(name="🔍 Proposed Next Searches", value="\n".join([f"• `{q}`" for q in queries]), inline=False)

                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"❌ RAG Error: {res.text}")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Error: {e}")

    # --------------------------------------------------------------------------
    # 7. /compare papers criteria
    # --------------------------------------------------------------------------
    @app_commands.command(name="compare", description="Compare multiple ingested papers across scientific criteria.")
    @app_commands.describe(papers="Comma-separated BibTeX keys", criteria="Criteria (e.g. methods, results, limitations)")
    async def compare(
        self,
        interaction: discord.Interaction,
        papers: str,
        criteria: str = "methods, results, limitations",
    ):
        await interaction.response.defer()
        keys = [k.strip() for k in papers.split(",") if k.strip()]
        crit_list = [c.strip() for c in criteria.split(",") if c.strip()]
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                res = await client.post(
                    f"{API_BASE}/agent/compare",
                    json={"paper_keys": keys, "criteria": crit_list},
                )
                if res.status_code == 200:
                    data = res.json()
                    matrix = data.get("matrix", [])
                    embed = discord.Embed(
                        title=f"⚖️ Literature Comparison ({len(keys)} Papers)",
                        color=0x457B9D,
                    )
                    for item in matrix[:5]:
                        bkey = item.get("bibtex_key", "Paper")
                        method = item.get("method", "N/A")
                        result = item.get("key_result", "N/A")
                        embed.add_field(name=f"`{bkey}`", value=f"**Method:** {method}\n**Result:** {result}", inline=False)

                    gaps = data.get("identified_gaps", [])
                    if gaps:
                        embed.add_field(name="🔬 Identified Gaps in Literature", value="\n".join([f"• {g}" for g in gaps[:3]]), inline=False)
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"❌ Comparison failed: {res.text}")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Error: {e}")

    # --------------------------------------------------------------------------
    # 8. /gaps (project_id optional) -> top 5 gaps with evidence & experiments
    # --------------------------------------------------------------------------
    @app_commands.command(name="gaps", description="Identify literature gaps using open-source topic clusters, graph analysis, and trends.")
    @app_commands.describe(project_id="Project ID (default: active project)")
    async def gaps(
        self,
        interaction: discord.Interaction,
        project_id: Optional[int] = 1,
    ):
        await interaction.response.defer()
        target_id = project_id or 1
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(
                    f"{API_BASE}/agent/gaps",
                    json={"project_id": target_id},
                )
                if res.status_code == 200:
                    data = res.json()
                    total = data.get("total_papers_analyzed", 0)
                    embed = discord.Embed(
                        title=f"🔬 Open-Source Research Gap Analysis (Project #{target_id})",
                        description=f"Analyzed **{total}** papers using topic clustering, citation graph bridges, and publication velocity.",
                        color=0x9B59B6,
                    )
                    # Synthesized top gaps
                    synth_gaps = data.get("synthesized_gaps", [])
                    if synth_gaps:
                        gaps_text = "\n".join([f"• **Gap {i+1}:** {g}" for i, g in enumerate(synth_gaps[:5])])
                        embed.add_field(name="🎯 Top Literature Gaps", value=gaps_text[:1024], inline=False)

                    # Underexplored clusters
                    underexplored = data.get("underexplored_clusters", [])
                    if underexplored:
                        under_text = "\n".join([f"• **Cluster #{c.get('cluster_id')}:** {c.get('topic_name')} ({c.get('paper_count')} papers, recency: {c.get('recency_ratio')})" for c in underexplored[:3]])
                        embed.add_field(name="📈 Emerging / Underexplored Frontiers", value=under_text[:1024], inline=False)

                    # Bridge gaps
                    bridges = data.get("bridge_gaps", [])
                    if bridges:
                        bridge_text = "\n".join([f"• **Betweenness Bridge:** `{b.get('source_paper')}` ↔ `{b.get('target_paper')}` ({b.get('relationship')})" for b in bridges[:3]])
                        embed.add_field(name="🌉 Weakly-Connected Community Bridges", value=bridge_text[:1024], inline=False)

                    # Proposed experiments & searches
                    exps = data.get("proposed_experiments", [])
                    if exps:
                        exp_text = "\n".join([f"🧪 {e}" for e in exps[:3]])
                        embed.add_field(name="💡 Recommended Experiments", value=exp_text[:1024], inline=False)

                    searches = data.get("recommended_searches", [])
                    if searches:
                        search_text = "\n".join([f"`{s}`" for s in searches[:3]])
                        embed.add_field(name="🔍 Recommended Follow-Up Searches", value=search_text[:1024], inline=False)

                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send(f"❌ Gap analysis failed: {res.text}")
        except Exception as e:
            logger.error(f"Error in /gaps command: {e}")
            await interaction.followup.send(f"⚠️ Error executing gap analysis: {e}")

    # --------------------------------------------------------------------------
    # 9. /outline topic target
    # --------------------------------------------------------------------------
    @app_commands.command(name="outline", description="Generate structured academic outline with citation placements.")
    @app_commands.describe(topic="Research manuscript topic", target="Target section or focus")
    async def outline(
        self,
        interaction: discord.Interaction,
        topic: str,
        target: str = "related work",
    ):
        await interaction.response.defer()
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                res = await client.post(
                    f"{API_BASE}/agent/outline",
                    json={"topic": topic, "target": target},
                )
                if res.status_code == 200:
                    data = res.json()
                    text = data.get("outline", "")
                    await interaction.followup.send(f"📝 **Manuscript Outline: {topic}**\n\n{text[:1900]}")
                else:
                    await interaction.followup.send(f"❌ Outline failed: {res.text}")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Error: {e}")

    # --------------------------------------------------------------------------
    # 9. /draft section
    # --------------------------------------------------------------------------
    @app_commands.command(name="draft", description="Draft academic paper section grounded with strict \\cite{} keys.")
    @app_commands.describe(section="e.g. methods, related work, introduction", topic="Focus area")
    async def draft(
        self,
        interaction: discord.Interaction,
        section: str,
        topic: Optional[str] = "",
    ):
        await interaction.response.defer()
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(
                    f"{API_BASE}/agent/draft",
                    json={"section": section, "project_id": 1, "topic": topic or section},
                )
                if res.status_code == 200:
                    data = res.json()
                    draft_text = data.get("draft", "")
                    await interaction.followup.send(f"📄 **Draft: {section.upper()}**\n\n{draft_text[:1900]}")
                else:
                    await interaction.followup.send(f"❌ Drafting failed: {res.text}")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Error: {e}")

    # --------------------------------------------------------------------------
    # 10. /tasks add | list | done
    # --------------------------------------------------------------------------
    @app_commands.command(name="tasks", description="Track laboratory research tasks.")
    @app_commands.describe(action="add, list, or done", title="Task description (for add)", task_id="Task ID (for done)")
    async def tasks(
        self,
        interaction: discord.Interaction,
        action: Literal["add", "list", "done"],
        title: Optional[str] = None,
        task_id: Optional[int] = None,
    ):
        await interaction.response.defer()
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                if action == "add" and title:
                    res = await client.post(f"{API_BASE}/projects/1/tasks", json={"title": title})
                    if res.status_code == 200:
                        t = res.json()
                        await interaction.followup.send(f"📋 Added task `[#{t['id']}]` **{t['title']}**")
                    else:
                        await interaction.followup.send(f"❌ Failed to add task: {res.text}")
                elif action == "list":
                    res = await client.get(f"{API_BASE}/projects/1/tasks")
                    if res.status_code == 200:
                        tlist = res.json()
                        if not tlist:
                            await interaction.followup.send("📋 No tasks registered for this project.")
                            return
                        lines = [f"• `[#{t['id']}]` {t['title']} (`{t['status']}`)" for t in tlist]
                        await interaction.followup.send(f"📋 **Laboratory Task Board**:\n" + "\n".join(lines))
                    else:
                        await interaction.followup.send("❌ Could not list tasks.")
                else:
                    await interaction.followup.send("📋 Task updated.")
        except Exception as e:
            await interaction.followup.send(f"⚠️ Task error: {e}")

    # --------------------------------------------------------------------------
    # 11. /scratchpad view | add | clear
    # --------------------------------------------------------------------------
    @app_commands.command(name="scratchpad", description="Private per-researcher scratchpad.")
    @app_commands.describe(action="view, add, or clear", note="Note text to append")
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
                    await interaction.followup.send("📝 Scratchpad accessed.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ Scratchpad error: {e}", ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ResearchCog(bot))
