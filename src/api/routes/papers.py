from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.common.models import PaperMetadata, SearchQuery
from src.connectors.arxiv_connector import ArxivConnector
from src.connectors.crossref_connector import CrossrefConnector
from src.connectors.openalex_connector import OpenAlexConnector
from src.connectors.pubmed_connector import PubMedConnector
from src.connectors.semantic_scholar import SemanticScholarConnector
from src.storage.database import get_db
from src.storage.models import Paper, PaperAuthor, PaperChunk, PaperNote, PaperSection
from src.worker.tasks import PaperIngestionService

router = APIRouter(tags=["papers"])


class IngestRequest(BaseModel):
    identifier: str
    project_id: Optional[int] = None


@router.post("/search", response_model=List[PaperMetadata])
@router.post("/papers/search", response_model=List[PaperMetadata])
async def search_literature(req: SearchQuery):
    results: List[PaperMetadata] = []
    sources = set([s.lower() for s in req.sources])

    if "all" in sources or "arxiv" in sources:
        arxiv_client = ArxivConnector()
        results.extend(await arxiv_client.search(req.query, limit=req.max_results_per_source))
    if "all" in sources or "semanticscholar" in sources or "s2" in sources:
        s2_client = SemanticScholarConnector()
        results.extend(await s2_client.search(req.query, limit=req.max_results_per_source))
    if "all" in sources or "pubmed" in sources:
        pubmed_client = PubMedConnector()
        results.extend(await pubmed_client.search(req.query, limit=req.max_results_per_source))
    if "all" in sources or "openalex" in sources:
        alex_client = OpenAlexConnector()
        results.extend(await alex_client.search(req.query, limit=req.max_results_per_source))

    # Deduplicate results by title/bibtex key
    seen = set()
    deduped = []
    for p in results:
        if p.bibtex_key not in seen:
            seen.add(p.bibtex_key)
            deduped.append(p)

    return deduped[:req.max_results_per_source * 2]


@router.post("/papers/ingest")
async def ingest_paper(req: IngestRequest):
    service = PaperIngestionService()
    try:
        paper = await service.ingest(req.identifier, req.project_id)
        return {
            "status": "success",
            "paper_id": paper.id,
            "bibtex_key": paper.bibtex_key,
            "title": paper.title,
            "parse_status": paper.parse_status,
            "index_status": paper.index_status,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/papers/library")
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
            "parse_status": p.parse_status,
            "index_status": p.index_status,
        }
        for p in papers
    ]


@router.get("/papers/{bibtex_key}")
async def get_paper(bibtex_key: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Paper).where(Paper.bibtex_key == bibtex_key)
    res = await db.execute(stmt)
    paper = res.scalar_one_or_none()
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper '{bibtex_key}' not found in library.")

    # Fetch authors
    auth_stmt = select(PaperAuthor).where(PaperAuthor.paper_id == paper.id).order_by(PaperAuthor.ordinal_order.asc())
    auth_res = await db.execute(auth_stmt)
    authors = [a.author_name for a in auth_res.scalars().all()]

    return {
        "id": paper.id,
        "bibtex_key": paper.bibtex_key,
        "title": paper.title,
        "authors": authors,
        "abstract": paper.abstract,
        "year": paper.year,
        "venue": paper.venue,
        "doi": paper.doi,
        "arxiv_id": paper.arxiv_id,
        "citation_count": paper.citation_count,
        "parse_status": paper.parse_status,
        "index_status": paper.index_status,
        "pdf_url": paper.pdf_url,
    }


@router.get("/papers/{bibtex_key}/note")
async def get_paper_note(
    bibtex_key: str,
    project_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(PaperNote).join(Paper).where(Paper.bibtex_key == bibtex_key)
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
