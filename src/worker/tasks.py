import asyncio
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
from src.connectors.pubmed_connector import PubMedConnector
from src.connectors.semantic_scholar import SemanticScholarConnector
from src.ingestion.chunker import AcademicChunker
from src.ingestion.downloader import PDFDownloader
from src.ingestion.grobid_parser import GrobidParser
from src.ingestion.pymupdf_parser import PyMuPDFParser
from src.storage.database import async_session_maker
from src.storage.models import Paper, PaperAuthor, PaperNote, PaperSection
from src.storage.object_store import ObjectStore
from src.storage.vector_store import VectorStore

logger = setup_logger("hermes.worker.tasks")


class PaperIngestionService:
    """End-to-end ingestion pipeline: Resolve metadata -> Download -> Parse (GROBID/PyMuPDF) -> Index -> Extract Note."""

    def __init__(self) -> None:
        self.arxiv = ArxivConnector()
        self.s2 = SemanticScholarConnector()
        self.crossref = CrossrefConnector()
        self.pubmed = PubMedConnector()
        self.downloader = PDFDownloader()
        self.grobid = GrobidParser()
        self.pymupdf = PyMuPDFParser()
        self.chunker = AcademicChunker()
        self.vector_store = VectorStore()
        self.reader = ReaderAgent(LLMClient())

    async def ingest(self, identifier: str, project_id: Optional[int] = None) -> Paper:
        clean_id = identifier.strip()
        logger.info(f"Starting ingestion for: {clean_id}")

        # 1. Resolve Paper Metadata
        metadata = await self._resolve_metadata(clean_id)
        if not metadata:
            raise IngestionError(f"Could not resolve metadata for identifier: {clean_id}")

        async with async_session_maker() as session:
            # Check if paper already exists
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
                )
                session.add(paper)
                await session.flush()

                # Save authors
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

            # 2. Download PDF if URL available and not yet stored
            pdf_bytes = None
            if metadata.pdf_url and not paper.storage_pdf_path:
                try:
                    storage_path = await self.downloader.download_and_store(
                        metadata.pdf_url, metadata.bibtex_key
                    )
                    paper.storage_pdf_path = storage_path
                    await session.commit()
                except Exception as e:
                    logger.warning(f"Could not download PDF from {metadata.pdf_url}: {e}")

            # Fetch PDF bytes for parsing
            if paper.storage_pdf_path:
                pdf_bytes = await self.downloader.object_store.get_pdf(paper.storage_pdf_path)

            # 3. Parse Sections: Try GROBID first, then PyMuPDF fallback
            sections_content = []
            if pdf_bytes:
                if await self.grobid.is_available():
                    try:
                        logger.info(f"Parsing {paper.bibtex_key} with GROBID...")
                        sections_content = await self.grobid.parse_pdf(pdf_bytes)
                    except Exception as e:
                        logger.warning(f"GROBID failed ({e}), falling back to PyMuPDF.")
                        sections_content = self.pymupdf.parse_pdf(pdf_bytes)
                else:
                    logger.info("GROBID service offline, parsing with PyMuPDF.")
                    sections_content = self.pymupdf.parse_pdf(pdf_bytes)

            # 4. Save sections and index chunks in Qdrant
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

                # Chunk and index in vector store
                chunks = self.chunker.chunk_section(sec, paper.id, paper.bibtex_key)
                for c in chunks:
                    await self.vector_store.index_chunk(
                        paper_id=paper.id,
                        bibtex_key=paper.bibtex_key,
                        section_name=c["section_name"],
                        heading=c["heading"],
                        text_content=c["text_content"],
                        page_number=c["page_number"],
                        project_id=project_id,
                    )

            if sections_content:
                paper.is_parsed = True
                paper.is_indexed = True
                await session.commit()

            # 5. Extract structured note with ReaderAgent
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

            return paper

    async def _resolve_metadata(self, identifier: str) -> Optional[PaperMetadata]:
        # Case 1: arXiv ID (e.g. 2301.00234 or arxiv.org/abs/2301.00234)
        arxiv_match = re.search(r"(?:arxiv\.org/(?:abs|pdf)/)?([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)", identifier, re.I)
        if arxiv_match:
            arxiv_id = arxiv_match.group(1)
            logger.info(f"Detected arXiv ID: {arxiv_id}")
            meta = await self.arxiv.get_by_id(arxiv_id)
            if meta:
                return meta

        # Case 2: DOI (e.g. 10.1145/... or doi.org/...)
        doi_match = re.search(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", identifier, re.I)
        if doi_match:
            doi = doi_match.group(0)
            logger.info(f"Detected DOI: {doi}")
            meta = await self.crossref.get_by_id(doi)
            if meta:
                return meta

        # Case 3: PMID (e.g. pmid:12345678 or purely numeric under 9 digits)
        if identifier.lower().startswith("pmid:"):
            pmid = identifier.split(":")[-1].strip()
            return await self.pubmed.get_by_id(pmid)

        # Case 4: Title search fallback via Semantic Scholar
        results = await self.s2.search(identifier, limit=1)
        if results:
            return results[0]

        # Case 5: Title search via arXiv
        arx_results = await self.arxiv.search(identifier, limit=1)
        if arx_results:
            return arx_results[0]

        return None
