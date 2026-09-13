from typing import Any, Dict, List, Optional
import httpx
from src.common.logging import setup_logger
from src.common.models import Author, PaperMetadata
from src.config.settings import get_settings
from src.connectors.base import BaseConnector, generate_bibtex_key

logger = setup_logger("hermes.connectors.s2")

S2_BASE_URL = "https://api.semanticscholar.org/graph/v1"
FIELDS = "title,abstract,authors,year,venue,citationCount,openAccessPdf,externalIds"


class SemanticScholarConnector(BaseConnector):
    name = "semanticscholar"

    def __init__(self) -> None:
        self.settings = get_settings()

    def _get_headers(self) -> Dict[str, str]:
        headers = {"User-Agent": "HermesAcademicAgent/1.0"}
        if self.settings.SEMANTIC_SCHOLAR_API_KEY:
            headers["x-api-key"] = self.settings.SEMANTIC_SCHOLAR_API_KEY
        return headers

    async def search(self, query: str, limit: int = 5) -> List[PaperMetadata]:
        url = f"{S2_BASE_URL}/paper/search"
        params = {"query": query, "limit": limit, "fields": FIELDS}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(url, params=params, headers=self._get_headers())
                if res.status_code == 200:
                    data = res.json()
                    papers = []
                    for item in data.get("data", []):
                        paper = self._convert_to_model(item)
                        if paper:
                            papers.append(paper)
                    return papers
                else:
                    logger.warning(f"S2 search returned status {res.status_code}")
        except Exception as e:
            logger.error(f"Error querying Semantic Scholar: {e}")
        return []

    async def get_by_id(self, paper_id: str) -> Optional[PaperMetadata]:
        url = f"{S2_BASE_URL}/paper/{paper_id}"
        params = {"fields": FIELDS}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(url, params=params, headers=self._get_headers())
                if res.status_code == 200:
                    return self._convert_to_model(res.json())
        except Exception as e:
            logger.error(f"Error fetching S2 paper {paper_id}: {e}")
        return None

    def _convert_to_model(self, data: Dict[str, Any]) -> Optional[PaperMetadata]:
        title = data.get("title")
        if not title:
            return None

        authors = [
            Author(name=a.get("name", "Unknown"))
            for a in data.get("authors", [])
            if a.get("name")
        ]
        first_author = authors[0].name if authors else "Author"
        year = data.get("year")
        bibtex_key = generate_bibtex_key(first_author, year, title)

        external_ids = data.get("externalIds") or {}
        doi = external_ids.get("DOI")
        arxiv_id = external_ids.get("ArXiv")
        pmid = external_ids.get("PubMed")

        open_access = data.get("openAccessPdf") or {}
        pdf_url = open_access.get("url")

        return PaperMetadata(
            bibtex_key=bibtex_key,
            title=title,
            authors=authors,
            abstract=data.get("abstract") or "",
            year=year,
            venue=data.get("venue") or "Academic Venue",
            doi=doi,
            arxiv_id=arxiv_id,
            pmid=pmid,
            citation_count=data.get("citationCount") or 0,
            pdf_url=pdf_url,
            source="semanticscholar",
        )
