from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.models import PaperMetadata, SearchQuery
from src.connectors.arxiv_connector import ArxivConnector
from src.connectors.semantic_scholar import SemanticScholarConnector
from src.storage.database import get_db
from src.storage.models import Paper, PaperNote, PaperSection
from src.worker.tasks import PaperIngestionService

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("/search", response_model=List[PaperMetadata])
async def search_literature(
    query: str = Query(..., description="Academic search terms"),
    source: str = Query("all", description="arxiv, semanticscholar, or all"),
    limit: int = Query(5, ge=1, le=20),
):
    results: List[PaperMetadata] = []
    if source in ("arxiv", "all"):
        arxiv_client = ArxivConnector()
        results.extend(await arxiv_client.search(query, limit=limit))
    if source in ("semanticscholar", "all"):
        s2_client = SemanticScholarConnector()
        results.extend(await s2_client.search(query, limit=limit))

    return results[:limit]


@router.post("/ingest")
async def ingest_paper(
    identifier: str = Query(..., description="arXiv ID, DOI, URL, or PMID"),
    project_id: Optional[int] = Query(None),
):
    service = PaperIngestionService()
    try:
        paper = await service.ingest(identifier, project_id)
        return {
            "status": "success",
            "paper_id": paper.id,
            "bibtex_key": paper.bibtex_key,
            "title": paper.title,
            "is_parsed": paper.is_parsed,
            "is_indexed": paper.is_indexed,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/library")
async def list_library(
    query: Optional[str] = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Paper)
    if query:
        stmt = stmt.where(Paper.title.ilike(f"%{query}%") | Paper.bibtex_key.ilike(f"%{query}%"))
    stmt = stmt.order_by(Paper.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    papers = res.scalars().all()

    return [
        {
            "id": p.id,
            "bibtex_key": p.bibtex_key,
            "title": p.title,
            "venue": p.venue,
            "year": p.year,
            "citation_count": p.citation_count,
            "is_parsed": p.is_parsed,
        }
        for p in papers
    ]


@router.get("/{bibtex_key}/note")
async def get_paper_note(
    bibtex_key: str,
    project_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(PaperNote)
        .join(Paper)
        .where(Paper.bibtex_key == bibtex_key)
    )
    if project_id:
        stmt = stmt.where(PaperNote.project_id == project_id)

    res = await db.execute(stmt)
    note = res.scalar_one_or_none()
    if not note:
        raise HTTPException(status_code=404, detail=f"No structured note found for {bibtex_key}")

    return {
        "bibtex_key": bibtex_key,
        "problem": note.problem,
        "key_idea": note.key_idea,
        "method_details": note.method_details,
        "datasets": note.datasets,
        "metrics": note.metrics,
        "results": note.results,
        "limitations": note.limitations,
        "reproducibility_notes": note.reproducibility_notes,
        "important_quotes": note.important_quotes,
    }
