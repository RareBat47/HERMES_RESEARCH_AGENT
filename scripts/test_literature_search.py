import asyncio
from pathlib import Path
import sys

# Ensure repository root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table
from src.connectors.arxiv_connector import ArxivConnector
from src.connectors.semantic_scholar import SemanticScholarConnector

console = Console()


async def search_and_display(query: str):
    console.print(f"\n[bold cyan]Hermes Literature Search Engine[/bold cyan]")
    console.print(f"Query: [yellow]\"{query}\"[/yellow]\n")

    arxiv = ArxivConnector()
    s2 = SemanticScholarConnector()

    console.print("[dim]Querying arXiv API and Semantic Scholar Academic Graph...[/dim]")
    arxiv_results, s2_results = await asyncio.gather(
        arxiv.search(query, limit=3),
        s2.search(query, limit=3),
        return_exceptions=True,
    )

    table = Table(title=f"Retrieved Literature: {query}", show_header=True, header_style="bold magenta")
    table.add_column("Source", style="cyan", width=12)
    table.add_column("BibTeX Key", style="green", width=22)
    table.add_column("Title", style="white", width=45)
    table.add_column("Year", style="yellow", width=6)
    table.add_column("Citations", style="blue", width=10)

    if isinstance(arxiv_results, list):
        for p in arxiv_results:
            table.add_row("arXiv", p.bibtex_key, p.title[:45], str(p.year or "N/A"), str(p.citation_count))

    if isinstance(s2_results, list):
        for p in s2_results:
            table.add_row("S2 Graph", p.bibtex_key, p.title[:45], str(p.year or "N/A"), str(p.citation_count))

    console.print(table)


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "retrieval augmented generation"
    asyncio.run(search_and_display(q))
