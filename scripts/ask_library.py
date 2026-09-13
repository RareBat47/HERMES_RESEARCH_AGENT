import asyncio
from pathlib import Path
import sys

# Ensure repository root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.panel import Panel
from src.agent.graph import ResearchBrain
from src.storage.database import init_db

console = Console()


async def main():
    if len(sys.argv) < 2:
        console.print("[bold red]Usage:[/bold red] python scripts/ask_library.py \"<your academic question>\" [project_id]")
        sys.exit(1)

    question = sys.argv[1]
    project_id = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    console.print(f"\n[bold cyan]Hermes Evidence-Grounded Research QA[/bold cyan]")
    console.print(f"Question: [yellow]\"{question}\"[/yellow]\n")

    await init_db()
    brain = ResearchBrain()

    console.print("[dim]Retrieving relevant library passages and checking citation grounding...[/dim]")
    answer = await brain.ask_library(question, project_id=project_id)

    status_style = "bold green" if answer.is_grounded else "bold yellow"
    console.print(Panel(answer.answer, title=f"[{status_style}]Hermes Answer (Grounded: {answer.is_grounded})[/{status_style}]", border_style="cyan"))

    if answer.citations:
        console.print("\n[bold magenta]Cited Passages & Exact Quotes:[/bold magenta]")
        for c in answer.citations:
            console.print(f"  • [green]\\cite{{{c.bibtex_key}}}[/green] ({c.section_hint or 'Section'}, p.{c.page_hint or 1}):")
            console.print(f"    [dim]\"{c.exact_quote}\"[/dim]")

    if not answer.is_grounded:
        console.print("\n[bold red]⚠️ Unsupported Claims / Literature Gaps:[/bold red]")
        for u in answer.unsupported_claims:
            console.print(f"  • {u}")
        if answer.proposed_search_queries:
            console.print("\n[bold yellow]Recommended Next Searches:[/bold yellow]")
            for q in answer.proposed_search_queries:
                console.print(f"  • [cyan]{q}[/cyan]")


if __name__ == "__main__":
    asyncio.run(main())
