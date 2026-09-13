import asyncio
import json
import re
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.agent.llm_client import LLMClient
from src.agent.roles.reader import ReaderAgent
from src.common.exceptions import IngestionError
from src.common.logging import setup_logger
from src.common.models import PaperMetadata
from src.connectors.arxiv_connector import ArxivConnector
from src.connectors.crossref_connector import CrossrefConnector
from src.connectors.openalex_connector import OpenAlexConnector
from src.connectors.pubmed_connector import PubMedConnector
from src.connectors.semantic_scholar import SemanticScholarConnector
from src.ingestion.chunker import AcademicChunker
from src.ingestion.downloader import PDFDownloader
from src.ingestion.grobid_parser import GrobidParser
from src.ingestion.pymupdf_parser import PyMuPDFParser
from src.storage.database import async_session_maker
from src.storage.models import IngestionJob, Paper, PaperAuthor, PaperChunk, PaperNote, PaperSection
from src.storage.object_store import ObjectStore
from src.storage.vector_store import VectorStore

logger = setup_logger("hermes.worker.tasks")


class PaperIngestionService:
    """Robust background ingestion: IngestionJob tracking -> Download -> TEI/PyMuPDF -> Chunks in DB & Qdrant -> Reader."""

    def __init__(self) -> None:
        self.arxiv = ArxivConnector()
        self.s2 = SemanticScholarConnector()
        self.crossref = CrossrefConnector()
        self.pubmed = PubMedConnector()
        self.openalex = OpenAlexConnector()
        self.downloader = PDFDownloader()
        self.grobid = GrobidParser()
        self.pymupdf = PyMuPDFParser()
        self.chunker = AcademicChunker()
        self.vector_store = VectorStore()
        self.reader = ReaderAgent(LLMClient())

    async def create_job(self, identifier: str, project_id: Optional[int] = None) -> IngestionJob:
        async with async_session_maker() as session:
            job = IngestionJob(
                identifier=identifier.strip(),
                project_id=project_id,
                status="pending",
                progress=0,
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            return job

    async def update_job_progress(self, job_id: int, status: str, progress: int, error_message: str = None, bibtex_key: str = None) -> None:
        async with async_session_maker() as session:
            stmt = select(IngestionJob).where(IngestionJob.id == job_id)
            res = await session.execute(stmt)
            job = res.scalar_one_or_none()
            if job:
                job.status = status
                job.progress = progress
                if error_message:
                    job.error_message = error_message
                if bibtex_key:
                    job.paper_bibtex_key = bibtex_key
                await session.commit()

    async def ingest(self, identifier: str, project_id: Optional[int] = None, job_id: Optional[int] = None) -> Paper:
        clean_id = identifier.strip()
        logger.info(f"Starting paper ingestion for: {clean_id} (Job ID: {job_id})")

        if not job_id:
            job = await self.create_job(clean_id, project_id)
            job_id = job.id

        try:
            # 1. Resolve Metadata
            await self.update_job_progress(job_id, status="resolving_metadata", progress=15)
            metadata = await self._resolve_metadata(clean_id)
            if not metadata:
                raise IngestionError(f"Could not resolve metadata for identifier: {clean_id}")

            await self.update_job_progress(job_id, status="downloading", progress=30, bibtex_key=metadata.bibtex_key)

            async with async_session_maker() as session:
                stmt = select(Paper).where(Paper.bibtex_key == metadata.bibtex_key)
                res = await session.execute(stmt)
                paper = res.scalar_one_or_none()

                if not paper:
                    paper = Paper(
                        bibtex_key=metadata.bibtex_key,
                        title=metadata.title,
                        abstract=metadata.abstract,
                        year=metadata.year,
                        venue=metadata.venue,
                        doi=metadata.doi,
                        arxiv_id=metadata.arxiv_id,
                        pmid=metadata.pmid,
                        citation_count=metadata.citation_count,
                        pdf_url=metadata.pdf_url,
                        parse_status="pending",
                        index_status="pending",
                    )
                    session.add(paper)
                    await session.flush()

                    for idx, a in enumerate(metadata.authors):
                        author_record = PaperAuthor(
                            paper_id=paper.id,
                            author_name=a.name,
                            affiliation=a.affiliation,
                            ordinal_order=idx,
                        )
                        session.add(author_record)
                    await session.commit()
                    await session.refresh(paper)

                # 2. Download PDF
                pdf_bytes = None
                if metadata.pdf_url and not paper.pdf_object_path:
                    try:
                        storage_path = await self.downloader.download_and_store(
                            metadata.pdf_url, metadata.bibtex_key
                        )
                        paper.pdf_object_path = storage_path
                        await session.commit()
                    except Exception as e:
                        logger.warning(f"Could not download PDF from {metadata.pdf_url}: {e}")

                if paper.pdf_object_path:
                    pdf_bytes = await self.downloader.object_store.get_pdf(paper.pdf_object_path)

                # 3. Parse Sections: GROBID primary, PyMuPDF fallback
                await self.update_job_progress(job_id, status="parsing", progress=50)
                sections_content = []
                if pdf_bytes:
                    if await self.grobid.is_available():
                        try:
                            logger.info(f"Parsing {paper.bibtex_key} with GROBID...")
                            sections_content = await self.grobid.parse_pdf(pdf_bytes)
                        except Exception as e:
                            logger.warning(f"GROBID failed ({e}), using PyMuPDF fallback.")
                            sections_content = self.pymupdf.parse_pdf(pdf_bytes)
                    else:
                        logger.info("GROBID service offline, using PyMuPDF parser.")
                        sections_content = self.pymupdf.parse_pdf(pdf_bytes)

                # Fallback to abstract if no sections extracted
                if not sections_content:
                    from src.common.models import PaperSectionContent
                    sections_content = [
                        PaperSectionContent(
                            section_name="Abstract",
                            heading="Abstract",
                            text_content=paper.abstract or paper.title,
                            page_number=1,
                        )
                    ]

                # 4. Save Sections, Chunks in Postgres & Vector Embeddings in Qdrant
                await self.update_job_progress(job_id, status="indexing", progress=75)
                accumulated_text_for_reader = []
                for sec in sections_content:
                    accumulated_text_for_reader.append(f"[{sec.heading}]\n{sec.text_content}")
                    sec_record = PaperSection(
                        paper_id=paper.id,
                        section_name=sec.section_name,
                        heading=sec.heading,
                        text_content=sec.text_content,
                        page_number=sec.page_number or 1,
                    )
                    session.add(sec_record)
                    await session.flush()

                    # Explicit PaperChunk persistence
                    chunks = self.chunker.chunk_section(
                        section=sec,
                        paper_id=paper.id,
                        bibtex_key=paper.bibtex_key,
                        section_id=sec_record.id,
                    )
                    for c in chunks:
                        point_id = await self.vector_store.index_chunk(
                            paper_id=paper.id,
                            bibtex_key=paper.bibtex_key,
                            section_name=c["section_name"],
                            heading=c["heading"],
                            text_content=c["text"],
                            page_number=c["page_number"],
                            project_id=project_id,
                            char_start=c["char_start"],
                            char_end=c["char_end"],
                        )
                        chunk_record = PaperChunk(
                            paper_id=paper.id,
                            section_id=sec_record.id,
                            chunk_index=c["chunk_index"],
                            text=c["text"],
                            char_start=c["char_start"],
                            char_end=c["char_end"],
                            page_number=c["page_number"],
                            qdrant_point_id=point_id,
                            embedding_model=self.vector_store.settings.EMBEDDING_MODEL,
                        )
                        session.add(chunk_record)

                paper.parse_status = "parsed"
                paper.index_status = "indexed"
                await session.commit()

                # 5. Extract Structured Note with ReaderAgent
                await self.update_job_progress(job_id, status="extracting_notes", progress=90)
                full_context = "\n\n".join(accumulated_text_for_reader)
                note = await self.reader.extract_note(
                    bibtex_key=paper.bibtex_key,
                    title=paper.title,
                    abstract=paper.abstract,
                    sections_text=full_context,
                )

                if project_id is not None:
                    note_record = PaperNote(
                        paper_id=paper.id,
                        project_id=project_id,
                        is_shared=True,
                        problem=note.problem,
                        key_idea=note.key_idea,
                        method_details=note.method_details,
                        datasets={"datasets": note.datasets},
                        metrics={"metrics": note.metrics},
                        results=note.results,
                        limitations=note.limitations,
                        reproducibility_notes=note.reproducibility_notes,
                        important_quotes={"quotes": note.important_quotes},
                    )
                    session.add(note_record)
                    await session.commit()

                await self.update_job_progress(job_id, status="completed", progress=100, bibtex_key=paper.bibtex_key)
                logger.info(f"Ingestion job {job_id} completed successfully for {paper.bibtex_key}")
                return paper

        except Exception as e:
            logger.error(f"Ingestion failed for {clean_id} (Job ID {job_id}): {e}")
            await self.update_job_progress(job_id, status="failed", progress=0, error_message=str(e))
            raise

    async def _resolve_metadata(self, identifier: str) -> Optional[PaperMetadata]:
        # arXiv match
        arxiv_match = re.search(r"(?:arxiv\.org/(?:abs|pdf)/)?([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)", identifier, re.I)
        if arxiv_match:
            arxiv_id = arxiv_match.group(1)
            meta = await self.arxiv.get_by_id(arxiv_id)
            if meta:
                return meta

        # DOI match
        doi_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", identifier, re.I)
        if doi_match:
            doi = doi_match.group(0)
            meta = await self.crossref.get_by_id(doi)
            if meta:
                return meta

        # PMID match
        if identifier.lower().startswith("pmid:"):
            pmid = identifier.split(":")[-1].strip()
            return await self.pubmed.get_by_id(pmid)

        # OpenAlex match (W...)
        if identifier.upper().startswith("W") and identifier[1:].isdigit():
            meta = await self.openalex.get_by_id(identifier)
            if meta:
                return meta

        # Title lookup via Semantic Scholar
        results = await self.s2.search(identifier, limit=1)
        if results:
            return results[0]

        # Title lookup via OpenAlex
        alex_results = await self.openalex.search(identifier, limit=1)
        if alex_results:
            return alex_results[0]

        # Title lookup via arXiv
        arx_results = await self.arxiv.search(identifier, limit=1)
        if arx_results:
            return arx_results[0]

        return None
