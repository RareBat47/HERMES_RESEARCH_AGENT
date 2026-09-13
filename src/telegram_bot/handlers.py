import json
from typing import Optional
import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from src.common.logging import setup_logger
from src.config.settings import get_settings
from src.telegram_bot.security import restricted

logger = setup_logger("hermes.telegram.handlers")
settings = get_settings()
API_BASE = "http://localhost:8000"


@restricted
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Welcome message and system overview."""
    user = update.effective_user
    uid_str = f"`{user.id}`" if user else "Unknown"
    text = (
        "🏛️ *Welcome to Hermes Academic Research Agent*\n\n"
        "I am your collaborative laboratory assistant powered by **Cohere** "
        "(`command-r-plus`, `embed-v3`, `rerank-v3`) with **open-source gap finding** "
        "and strict citation grounding.\n\n"
        "📚 *Primary Academic Commands*:\n"
        "• `/search <query>` — Multi-source discovery (arXiv, S2, PubMed, OpenAlex)\n"
        "• `/add_paper <id>` — Ingest by arXiv ID, DOI, URL, or PMID\n"
        "• `/ask <question>` — Evidence-grounded QA citing exact library chunks\n"
        "• `/gaps` — Open-source gap finder (topic clusters, trends, graph bridges)\n"
        "• `/summarize <bibkey>` — Deep Reading Mode extraction\n"
        "• `/compare <key1,key2>` — Cross-paper comparison matrix\n"
        "• `/outline <topic>` — Manuscript outline with citation placements\n"
        "• `/draft <section>` — Academic section drafting\n"
        "• `/project [create|switch|truth]` — Long-term project memory\n"
        "• `/tasks [add|list|done]` — Laboratory task board\n"
        "• `/scratchpad [add|view|clear]` — Private per-researcher notes\n\n"
        f"👤 *Your Telegram User ID:* {uid_str}\n"
        "Type `/help` for detailed command syntax."
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")


@restricted
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detailed command reference."""
    text = (
        "📖 *Hermes Research Agent — Command Reference*\n\n"
        "🔍 *Discovery & Ingestion*:\n"
        "• `/search <query>` — e.g. `/search selective state space models`\n"
        "• `/add_paper <id>` — e.g. `/add_paper 1706.03762` or DOI\n"
        "• `/library` — Browse recently indexed papers\n\n"
        "🧠 *Evidence-Grounded Intelligence*:\n"
        "• `/ask <question>` — Answers citing verbatim quotes & pages\n"
        "• `/gaps` — Detects underexplored trends, graph bridges & experiments\n"
        "• `/summarize <key>` — Structured problem, method, metric, limitations\n"
        "• `/compare <key1,key2>` — Synthesis matrix of methods vs findings\n\n"
        "✍️ *Writing & Synthesis*:\n"
        "• `/outline <topic>` — e.g. `/outline Attention mechanisms survey`\n"
        "• `/draft <section>` — e.g. `/draft related work`\n\n"
        "🏛️ *Memory & Collaboration*:\n"
        "• `/project create <name>` — Create new research project\n"
        "• `/project truth` — View shared decisions and ground truth\n"
        "• `/tasks list` — View laboratory tasks\n"
        "• `/scratchpad add <note>` — Save private thought to your scratchpad"
    )
    await update.effective_message.reply_text(text, parse_mode="Markdown")


@restricted
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search academic literature with interactive inline buttons."""
    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.effective_message.reply_text("⚠️ Please provide a search query:\n`/search <query>`", parse_mode="Markdown")
        return

    status_msg = await update.effective_message.reply_text(f"🔍 Searching arXiv, Semantic Scholar, PubMed, and OpenAlex for *{query}*...", parse_mode="Markdown")

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            res = await client.post(
                f"{API_BASE}/search",
                json={"query": query, "sources": ["all"], "limit": 4},
            )
            if res.status_code != 200:
                await status_msg.edit_text(f"❌ Search failed: {res.text}")
                return

            data = res.json()
            papers = data.get("papers", [])
            if not papers:
                await status_msg.edit_text(f"No papers found for query: `{query}`.", parse_mode="Markdown")
                return

            await status_msg.delete()

            for i, p in enumerate(papers[:4], 1):
                title = p.get("title", "Untitled")
                year = p.get("year") or "N/A"
                venue = p.get("venue") or "Academic Source"
                abstract = p.get("abstract", "")[:320] + "..." if p.get("abstract") else "No abstract available."
                source = p.get("source_repository", "arXiv")
                bib_key = p.get("bibtex_key", f"Paper{i}")

                identifier = p.get("arxiv_id") or p.get("doi") or p.get("pdf_url") or bib_key

                msg = (
                    f"📄 *{i}. {title}*\n"
                    f"📅 *Year:* {year} | 🏛️ *Venue:* {venue} | 🌐 *Source:* `{source}`\n"
                    f"🔑 *BibTeX:* `{bib_key}`\n\n"
                    f"> {abstract}"
                )

                keyboard = [
                    [InlineKeyboardButton("📥 Add to Library", callback_data=f"ingest:{identifier[:60]}")]
                ]
                await update.effective_message.reply_text(
                    msg,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown",
                )
    except Exception as e:
        logger.error(f"Search command error: {e}")
        await update.effective_message.reply_text(f"⚠️ Search error: {e}")


@restricted
async def add_paper_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ingest paper by DOI, arXiv ID, URL, or PMID."""
    identifier = " ".join(context.args) if context.args else ""
    if not identifier:
        await update.effective_message.reply_text("⚠️ Usage: `/add_paper <arxiv_id | doi | url | pmid>`", parse_mode="Markdown")
        return

    status_msg = await update.effective_message.reply_text(f"⏳ Initiating ingestion pipeline for `{identifier}`...", parse_mode="Markdown")

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            res = await client.post(
                f"{API_BASE}/papers/ingest",
                json={"identifier": identifier.strip(), "project_id": 1},
            )
            if res.status_code == 200:
                data = res.json()
                job_id = data.get("job_id")
                await status_msg.edit_text(
                    f"✅ Ingestion job `#{job_id}` queued!\n\n"
                    f"Downloading PDF ➔ GROBID TEI Parsing ➔ Chunk Indexing in Qdrant (Cohere Embed v3).\n"
                    f"Identifier: `{identifier}`",
                    parse_mode="Markdown",
                )
            else:
                await status_msg.edit_text(f"❌ Ingestion failed: {res.text}")
    except Exception as e:
        logger.error(f"Add paper error: {e}")
        await status_msg.edit_text(f"⚠️ Ingestion error: {e}")


@restricted
async def ask_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Answer question strictly grounded in indexed library chunks with citations."""
    question = " ".join(context.args) if context.args else ""
    if not question:
        await update.effective_message.reply_text("⚠️ Usage: `/ask <research question>`", parse_mode="Markdown")
        return

    status_msg = await update.effective_message.reply_text("🧠 Retrieving candidate chunks from Qdrant and evaluating citations with Cohere...", parse_mode="Markdown")

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                f"{API_BASE}/agent/ask",
                json={"question": question, "project_id": 1, "scope": "library"},
            )
            if res.status_code != 200:
                await status_msg.edit_text(f"❌ Q&A error: {res.text}")
                return

            data = res.json()
            answer = data.get("answer", "No answer generated.")
            citations = data.get("citations", [])
            is_grounded = data.get("is_grounded", True)
            unsupported = data.get("unsupported_claims", [])
            searches = data.get("proposed_search_queries", [])

            response_text = f"🎯 *Research Answer*:\n\n{answer}\n\n"

            if citations:
                response_text += "📚 *Verbatim Citations & Evidence*:\n"
                for c in citations[:4]:
                    bkey = c.get("bibtex_key", "Source")
                    quote = c.get("exact_quote", "")
                    sec = c.get("section_hint") or "Section"
                    page = c.get("page_hint")
                    page_str = f", Page {page}" if page else ""
                    response_text += f"• `\\cite{{{bkey}}}` [{sec}{page_str}]:\n  _\"{quote[:200]}...\"_\n"

            if not is_grounded or unsupported:
                response_text += "\n⚠️ *Evidence Gap*: The current library did not contain sufficient grounding for some claims.\n"
                if searches:
                    response_text += "🔍 *Proposed Searches*:\n" + "\n".join([f"• `{s}`" for s in searches[:2]])

            await status_msg.edit_text(response_text[:4000], parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ask command error: {e}")
        await status_msg.edit_text(f"⚠️ Error executing grounded Q&A: {e}")


@restricted
async def gaps_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Open-source literature gap finder."""
    project_id = int(context.args[0]) if context.args and context.args[0].isdigit() else 1
    status_msg = await update.effective_message.reply_text("🔬 Running open-source topic clustering, NetworkX graph analysis, and trend velocity...", parse_mode="Markdown")

    try:
        async with httpx.AsyncClient(timeout=75.0) as client:
            res = await client.post(
                f"{API_BASE}/agent/gaps",
                json={"project_id": project_id},
            )
            if res.status_code != 200:
                await status_msg.edit_text(f"❌ Gap analysis failed: {res.text}")
                return

            data = res.json()
            total = data.get("total_papers_analyzed", 0)
            synth_gaps = data.get("synthesized_gaps", [])
            underexplored = data.get("underexplored_clusters", [])
            bridges = data.get("bridge_gaps", [])
            exps = data.get("proposed_experiments", [])
            searches = data.get("recommended_searches", [])

            text = f"🔬 *Open-Source Research Gap Analysis* (Project #{project_id})\n"
            text += f"Analyzed *{total}* papers via scikit-learn clustering & NetworkX centrality.\n\n"

            if synth_gaps:
                text += "🎯 *Top Literature Gaps*:\n"
                for i, g in enumerate(synth_gaps[:4], 1):
                    text += f"*{i}.* {g}\n\n"

            if underexplored:
                text += "📈 *Emerging / Underexplored Frontiers*:\n"
                for c in underexplored[:2]:
                    text += f"• *Cluster #{c.get('cluster_id')}:* {c.get('topic_name', 'Topic')} (Recency: {c.get('recency_ratio')})\n"
                text += "\n"

            if bridges:
                text += "🌉 *Weakly-Connected Community Bridges*:\n"
                for b in bridges[:2]:
                    text += f"• `{b.get('source_paper')}` ↔ `{b.get('target_paper')}` ({b.get('relationship')})\n"
                text += "\n"

            if exps:
                text += "💡 *Recommended Experiments*:\n"
                for e in exps[:2]:
                    text += f"• {e}\n"

            if searches:
                text += "\n🔍 *Follow-up Searches*:\n"
                for s in searches[:2]:
                    text += f"• `{s}`\n"

            await status_msg.edit_text(text[:4000], parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Gaps error: {e}")
        await status_msg.edit_text(f"⚠️ Gap analysis error: {e}")


@restricted
async def summarize_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """View structured Reading Mode note for a paper."""
    key = context.args[0] if context.args else ""
    if not key:
        await update.effective_message.reply_text("⚠️ Usage: `/summarize <bibtex_key>`", parse_mode="Markdown")
        return

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.get(f"{API_BASE}/papers/{key}")
            if res.status_code != 200:
                await update.effective_message.reply_text(f"❌ Paper `{key}` not found in library.", parse_mode="Markdown")
                return

            p = res.json()
            title = p.get("title", "Untitled")
            year = p.get("year") or "N/A"
            abstract = p.get("abstract", "No abstract.")[:500]

            msg = (
                f"📖 *Reading Mode: {key}*\n\n"
                f"📄 *Title:* {title}\n"
                f"📅 *Year:* {year} | 🏛️ *Venue:* {p.get('venue') or 'N/A'}\n"
                f"🔗 *DOI:* `{p.get('doi') or 'N/A'}`\n\n"
                f"📝 *Abstract Summary*:\n> {abstract}...\n\n"
                f"Status: `{p.get('parse_status')}` / Indexed: `{p.get('index_status')}`"
            )
            await update.effective_message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Summarize error: {e}")


@restricted
async def compare_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Compare multiple papers by BibTeX keys."""
    if not context.args or len(context.args) < 2:
        await update.effective_message.reply_text("⚠️ Usage: `/compare <key1> <key2> [key3]`", parse_mode="Markdown")
        return

    keys = [k.strip(",") for k in context.args]
    status_msg = await update.effective_message.reply_text(f"⚖️ Generating comparison matrix for: {', '.join(keys)}...")

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            res = await client.post(
                f"{API_BASE}/agent/compare",
                json={"paper_keys": keys},
            )
            if res.status_code == 200:
                data = res.json()
                matrix = data.get("matrix", [])
                gaps = data.get("identified_gaps", [])

                text = f"⚖️ *Literature Comparison Matrix ({len(keys)} Papers)*\n\n"
                for item in matrix[:4]:
                    bkey = item.get("bibtex_key", "Paper")
                    method = item.get("method", "N/A")
                    result = item.get("results", item.get("key_result", "N/A"))
                    text += f"• `{bkey}`:\n  *Method:* {method}\n  *Result:* {result}\n\n"

                if gaps:
                    text += "🔬 *Identified Gaps*:\n" + "\n".join([f"• {g}" for g in gaps[:2]])

                await status_msg.edit_text(text[:4000], parse_mode="Markdown")
            else:
                await status_msg.edit_text(f"❌ Comparison failed: {res.text}")
    except Exception as e:
        await status_msg.edit_text(f"⚠️ Comparison error: {e}")


@restricted
async def outline_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate structured manuscript outline."""
    topic = " ".join(context.args) if context.args else ""
    if not topic:
        await update.effective_message.reply_text("⚠️ Usage: `/outline <topic>`", parse_mode="Markdown")
        return

    status_msg = await update.effective_message.reply_text(f"📝 Generating outline for *{topic}*...", parse_mode="Markdown")
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            res = await client.post(
                f"{API_BASE}/agent/outline",
                json={"topic": topic, "target": "related work"},
            )
            if res.status_code == 200:
                outline = res.json().get("outline", "")
                await status_msg.edit_text(f"📝 *Manuscript Outline: {topic}*\n\n{outline[:3800]}", parse_mode="Markdown")
            else:
                await status_msg.edit_text(f"❌ Outline failed: {res.text}")
    except Exception as e:
        await status_msg.edit_text(f"⚠️ Outline error: {e}")


@restricted
async def draft_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Draft academic section grounded with BibTeX citations."""
    section = " ".join(context.args) if context.args else "related work"
    status_msg = await update.effective_message.reply_text(f"📄 Drafting section *{section}* with citation tags...", parse_mode="Markdown")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            res = await client.post(
                f"{API_BASE}/agent/draft",
                json={"section": section, "project_id": 1, "topic": section},
            )
            if res.status_code == 200:
                content = res.json().get("draft", "")
                await status_msg.edit_text(f"📄 *Draft: {section.upper()}*\n\n{content[:3800]}", parse_mode="Markdown")
            else:
                await status_msg.edit_text(f"❌ Drafting failed: {res.text}")
    except Exception as e:
        await status_msg.edit_text(f"⚠️ Draft error: {e}")


@restricted
async def tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Laboratory research task board."""
    args = context.args or ["list"]
    action = args[0].lower()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if action == "add" and len(args) > 1:
                title = " ".join(args[1:])
                res = await client.post(f"{API_BASE}/projects/1/tasks", json={"title": title})
                if res.status_code == 200:
                    t = res.json()
                    await update.effective_message.reply_text(f"📋 Added task `[#{t['id']}]` *{t['title']}*", parse_mode="Markdown")
                else:
                    await update.effective_message.reply_text(f"❌ Failed to add task: {res.text}")
            else:
                res = await client.get(f"{API_BASE}/projects/1/tasks")
                if res.status_code == 200:
                    tlist = res.json()
                    if not tlist:
                        await update.effective_message.reply_text("📋 No active tasks registered for this project.")
                        return
                    lines = [f"• `[#{t['id']}]` {t['title']} (`{t['status']}`)" for t in tlist]
                    await update.effective_message.reply_text("📋 *Laboratory Task Board*:\n" + "\n".join(lines), parse_mode="Markdown")
                else:
                    await update.effective_message.reply_text("❌ Could not fetch tasks.")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Task error: {e}")


@restricted
async def scratchpad_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Private per-researcher scratchpad."""
    user = update.effective_user
    args = context.args or ["view"]
    action = args[0].lower()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            if action == "add" and len(args) > 1:
                note = " ".join(args[1:])
                await client.post(
                    f"{API_BASE}/projects/user/{user.id}/scratchpad",
                    params={"username": user.username or "researcher"},
                    json={"note": note, "project_id": 1},
                )
                await update.effective_message.reply_text(f"📝 Appended to your private scratchpad:\n> {note}", parse_mode="Markdown")
            else:
                await update.effective_message.reply_text("📝 Scratchpad accessed.")
    except Exception as e:
        await update.effective_message.reply_text(f"⚠️ Scratchpad error: {e}")


async def inline_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle inline button clicks like [📥 Add to Library]."""
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()
    data = query.data

    if data.startswith("ingest:"):
        identifier = data.replace("ingest:", "").strip()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(
                    f"{API_BASE}/papers/ingest",
                    json={"identifier": identifier, "project_id": 1},
                )
                if res.status_code == 200:
                    job = res.json()
                    await query.edit_message_reply_markup(reply_markup=None)
                    await query.message.reply_text(
                        f"✅ Ingestion job `#{job.get('job_id')}` started for `{identifier}`!\n"
                        f"Downloading PDF ➔ GROBID TEI Parsing ➔ Qdrant Vector Indexing.",
                        parse_mode="Markdown",
                    )
                else:
                    await query.message.reply_text(f"❌ Failed to ingest: {res.text}")
        except Exception as e:
            await query.message.reply_text(f"⚠️ Ingestion trigger error: {e}")
