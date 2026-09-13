import asyncio
from pathlib import Path
import sys

# Ensure repository root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from src.storage.database import init_db
from src.worker.tasks import PaperIngestionService

console = Console()


async def main():
    if len(sys.argv) < 2:
        console.print("[bold red]Usage:[/bold red] python scripts/ingest_paper.py <arXiv-ID | DOI | URL | PMID> [project_id]")
        sys.exit(1)

    identifier = sys.argv[1]
    project_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    console.print(f"[bold cyan]Hermes Ingestion Pipeline[/bold cyan]")
    console.print(f"Target Identifier: [yellow]{identifier}[/yellow] (Project #{project_id})\n")

    await init_db()
    service = PaperIngestionService()

    try:
        console.print("[dim]Resolving metadata, downloading PDF, extracting sections, and generating embeddings...[/dim]")
        paper = await service.ingest(identifier, project_id=project_id)
        console.print(f"\n[bold green]✓ Successfully Ingested and Indexed![/bold green]")
        console.print(f"  • [cyan]Title:[/cyan] {paper.title}")
        console.print(f"  • [cyan]BibTeX Key:[/cyan] `{paper.bibtex_key}`")
        console.print(f"  • [cyan]Parser Status:[/cyan] {paper.parse_status}")
        console.print(f"  • [cyan]Index Status:[/cyan] {paper.index_status}")
        if paper.pdf_object_path:
            console.print(f"  • [cyan]Storage Path:[/cyan] {paper.pdf_object_path}")
    except Exception as e:
        console.print(f"[bold red]✗ Ingestion Failed:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
