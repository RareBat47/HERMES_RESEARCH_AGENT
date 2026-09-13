import asyncio
from pathlib import Path
import sys

# Ensure repository root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table
from src.connectors.arxiv_connector import ArxivConnector
from src.connectors.openalex_connector import OpenAlexConnector
from src.connectors.pubmed_connector import PubMedConnector
from src.connectors.semantic_scholar import SemanticScholarConnector

console = Console()


async def search_and_display(query: str):
    console.print(f"\n[bold cyan]Hermes Literature Search Engine[/bold cyan]")
    console.print(f"Query: [yellow]\"{query}\"[/yellow]\n")

    arxiv = ArxivConnector()
    s2 = SemanticScholarConnector()
    pubmed = PubMedConnector()
    openalex = OpenAlexConnector()

    console.print("[dim]Querying arXiv, Semantic Scholar, PubMed, and OpenAlex in parallel...[/dim]")
    results_list = await asyncio.gather(
        arxiv.search(query, limit=2),
        s2.search(query, limit=2),
        pubmed.search(query, limit=2),
        openalex.search(query, limit=2),
        return_exceptions=True,
    )

    table = Table(title=f"Retrieved Literature: {query}", show_header=True, header_style="bold magenta")
    table.add_column("Source", style="cyan", width=12)
    table.add_column("BibTeX Key", style="green", width=22)
    table.add_column("Title", style="white", width=45)
    table.add_column("Year", style="yellow", width=6)
    table.add_column("Citations", style="blue", width=10)

    for res in results_list:
        if isinstance(res, list):
            for p in res:
                table.add_row(p.source, p.bibtex_key, p.title[:45], str(p.year or "N/A"), str(p.citation_count))

    console.print(table)


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else "retrieval augmented generation"
    asyncio.run(search_and_display(q))
