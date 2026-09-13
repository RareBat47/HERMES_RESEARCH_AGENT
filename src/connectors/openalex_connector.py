from typing import Any, Dict, List, Optional
import httpx
from src.common.logging import setup_logger
from src.common.models import Author, PaperMetadata
from src.config.settings import get_settings
from src.connectors.base import BaseConnector, generate_bibtex_key

logger = setup_logger("hermes.connectors.openalex")

OPENALEX_BASE_URL = "https://api.openalex.org/works"


def reconstruct_abstract_from_inverted_index(inverted_index: Optional[Dict[str, List[int]]]) -> str:
    """Reconstruct standard abstract text from OpenAlex inverted index mapping."""
    if not inverted_index:
        return ""
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort(key=lambda x: x[0])
    return " ".join([word for _, word in word_positions])


class OpenAlexConnector(BaseConnector):
    name = "openalex"

    def __init__(self) -> None:
        self.settings = get_settings()

    def _get_headers(self) -> Dict[str, str]:
        email = self.settings.OPENALEX_EMAIL or "hermes.agent@example.com"
        return {"User-Agent": f"HermesAcademicAgent/1.0 (mailto:{email})"}

    async def search(self, query: str, limit: int = 5) -> List[PaperMetadata]:
        params = {
            "search": query,
            "per_page": limit,
            "mailto": self.settings.OPENALEX_EMAIL,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                res = await client.get(OPENALEX_BASE_URL, params=params, headers=self._get_headers())
                if res.status_code == 200:
                    results = res.json().get("results", [])
                    return [self._convert_to_model(item) for item in results if self._convert_to_model(item)]
        except Exception as e:
            logger.error(f"Error querying OpenAlex: {e}")
        return []

    async def get_by_id(self, identifier: str) -> Optional[PaperMetadata]:
        clean_id = identifier.strip()
        url = f"{OPENALEX_BASE_URL}/{clean_id}"
        params = {"mailto": self.settings.OPENALEX_EMAIL}
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                res = await client.get(url, params=params, headers=self._get_headers())
                if res.status_code == 200:
                    return self._convert_to_model(res.json())
        except Exception as e:
            logger.error(f"Error fetching OpenAlex paper {identifier}: {e}")
        return None

    def _convert_to_model(self, item: Dict[str, Any]) -> Optional[PaperMetadata]:
        title = item.get("title")
        if not title:
            return None

        authors: List[Author] = []
        for authorship in item.get("authorships", []):
            author_info = authorship.get("author", {})
            name = author_info.get("display_name")
            if name:
                authors.append(Author(name=name))

        first_author = authors[0].name if authors else "Author"
        year = item.get("publication_year")
        bibtex_key = generate_bibtex_key(first_author, year, title)

        abstract = reconstruct_abstract_from_inverted_index(item.get("abstract_inverted_index"))

        doi = item.get("doi")
        if doi and doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "")

        venue = None
        primary_location = item.get("primary_location") or {}
        source_info = primary_location.get("source") or {}
        venue = source_info.get("display_name")

        pdf_url = primary_location.get("pdf_url")
        citation_count = item.get("cited_by_count", 0)

        # External IDs
        ids = item.get("ids", {})
        pmid = ids.get("pmid")
        if pmid and pmid.startswith("https://pubmed.ncbi.nlm.nih.gov/"):
            pmid = pmid.replace("https://pubmed.ncbi.nlm.nih.gov/", "").rstrip("/")

        return PaperMetadata(
            bibtex_key=bibtex_key,
            title=title,
            authors=authors,
            abstract=abstract,
            year=year,
            venue=venue or "OpenAlex Academic Archive",
            doi=doi,
            pmid=pmid,
            citation_count=citation_count,
            pdf_url=pdf_url,
            source="openalex",
        )
