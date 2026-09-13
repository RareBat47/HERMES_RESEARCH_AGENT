from typing import Any, Callable, Dict, List
import discord
from src.discord_bot.ui.embeds import create_search_result_embed


class SearchPaginationView(discord.ui.View):
    """Interactive pagination view for browsing multi-source literature search results."""

    def __init__(self, papers: List[Dict[str, Any]], ingest_callback: Callable):
        super().__init__(timeout=180)
        self.papers = papers
        self.ingest_callback = ingest_callback
        self.current_idx = 0
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_button.disabled = (self.current_idx == 0)
        self.next_button.disabled = (self.current_idx >= len(self.papers) - 1)

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_idx > 0:
            self.current_idx -= 1
            self._update_buttons()
            embed = create_search_result_embed(self.papers[self.current_idx], self.current_idx + 1, len(self.papers))
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📥 Add to Library", style=discord.ButtonStyle.success)
    async def ingest_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        target_paper = self.papers[self.current_idx]
        key = target_paper.get("bibtex_key", "Paper")
        identifier = target_paper.get("doi") or target_paper.get("arxiv_id") or target_paper.get("title")

        await interaction.response.send_message(
            f"⏳ Queued ingestion for `{key}`... Ingesting PDF, running GROBID/PyMuPDF, and indexing passages.",
            ephemeral=True,
        )
        await self.ingest_callback(identifier)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_idx < len(self.papers) - 1:
            self.current_idx += 1
            self._update_buttons()
            embed = create_search_result_embed(self.papers[self.current_idx], self.current_idx + 1, len(self.papers))
            await interaction.response.edit_message(embed=embed, view=self)
