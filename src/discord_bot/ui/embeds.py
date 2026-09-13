from typing import Any, Dict, List, Optional
import discord

COLOR_PRIMARY = 0x2B2D42      # Deep Slate Navy
COLOR_SUCCESS = 0x2A9D8F      # Academic Teal
COLOR_WARNING = 0xE76F51      # Terra Cotta / Attention
COLOR_INFO = 0x457B9D         # Scholarly Blue
COLOR_MUTED = 0x8D99AE        # Subtle Gray


def create_search_result_embed(paper: Dict[str, Any], index: int, total: int) -> discord.Embed:
    """Generate a high-aesthetic Discord embed for literature search results."""
    title = paper.get("title", "Untitled Paper")
    bibtex_key = paper.get("bibtex_key", "UnknownKey")
    venue = paper.get("venue") or "Preprint / Academic Archive"
    year = paper.get("year") or "N/A"
    citations = paper.get("citation_count", 0)
    abstract = paper.get("abstract", "No abstract available.")

    embed = discord.Embed(
        title=f"📄 [{index}/{total}] {title}",
        description=f"*{abstract[:350]}...*" if len(abstract) > 350 else f"*{abstract}*",
        color=COLOR_INFO,
    )
    embed.add_field(name="Citation Key", value=f"`{bibtex_key}`", inline=True)
    embed.add_field(name="Venue & Year", value=f"{venue} ({year})", inline=True)
    embed.add_field(name="Citations", value=f"⭐ {citations}", inline=True)

    if paper.get("doi"):
        embed.add_field(name="DOI", value=f"[{paper['doi']}](https://doi.org/{paper['doi']})", inline=True)
    if paper.get("arxiv_id"):
        embed.add_field(name="arXiv", value=f"[{paper['arxiv_id']}](https://arxiv.org/abs/{paper['arxiv_id']})", inline=True)

    embed.set_footer(text="Hermes Academic Intelligence • Literature Pipeline")
    return embed


def create_reading_mode_embed(note: Dict[str, Any]) -> discord.Embed:
    """Generate a Reading Mode embed displaying structured contributions, methods, metrics, and quotes."""
    key = note.get("bibtex_key", "Paper")
    problem = note.get("problem", "N/A")
    idea = note.get("key_idea", "N/A")
    results = note.get("results", "N/A")
    limitations = note.get("limitations", "N/A")

    embed = discord.Embed(
        title=f"📖 Reading Mode: `{key}`",
        description=f"**Core Problem:** {problem}\n\n**Key Novelty:** {idea}",
        color=COLOR_SUCCESS,
    )

    if note.get("method_details"):
        embed.add_field(name="🔬 Methodology", value=note["method_details"][:600], inline=False)
    if results:
        embed.add_field(name="📊 Empirical Findings", value=results[:600], inline=False)
    if limitations:
        embed.add_field(name="⚠️ Limitations & Assumptions", value=limitations[:600], inline=False)

    quotes = note.get("important_quotes", {}).get("quotes", [])
    if quotes:
        quote_text = "\n".join([f"> *\"{q.get('quote', '')[:120]}...\"* (p.{q.get('page', '?')})" for q in quotes[:2]])
        embed.add_field(name="💬 Verbatim Evidence Passages", value=quote_text, inline=False)

    embed.set_footer(text="Hermes Reading Extractor • Evidence-Grounded")
    return embed


def create_citation_verification_embed(res: Dict[str, Any]) -> discord.Embed:
    """Generate an embed displaying citation verification and evidence matching."""
    verified = res.get("is_verified", False)
    claim = res.get("claim", "")
    passage = res.get("grounding_passage", "")
    critique = res.get("critique", "")
    score = res.get("similarity_score", 0.0)

    color = COLOR_SUCCESS if verified else COLOR_WARNING
    status_emoji = "✅ VERIFIED GROUNDING" if verified else "❌ UNGROUNDED / MISATTRIBUTED"

    embed = discord.Embed(
        title=f"{status_emoji} (Confidence: {score:.2f})",
        color=color,
    )
    embed.add_field(name="Author Claim", value=f"\"{claim}\"", inline=False)
    embed.add_field(name="Cited Paper Passage", value=f"> *\"{passage[:400]}...\"*", inline=False)
    embed.add_field(name="Critic Assessment", value=critique, inline=False)
    embed.set_footer(text="Hermes Critic Agent • Hallucination Defense")
    return embed
