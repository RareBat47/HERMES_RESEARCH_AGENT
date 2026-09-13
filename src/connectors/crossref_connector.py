from typing import Any, Dict, List, Optional
import httpx
from src.common.logging import setup_logger
from src.common.models import Author, PaperMetadata
from src.connectors.base import BaseConnector, generate_bibtex_key

logger = setup_logger("hermes.connectors.crossref")

CROSSREF_BASE_URL = "https://api.crossref.org/works"


class CrossrefConnector(BaseConnector):
    name = "crossref"

    async def search(self, query: str, limit: int = 5) -> List[PaperMetadata]:
        headers = {"User-Agent": "HermesAcademicAgent/1.0 (mailto:hermes.agent@example.com)"}
        params = {"query": query, "rows": limit}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(CROSSREF_BASE_URL, params=params, headers=headers)
                if res.status_code == 200:
                    items = res.json().get("message", {}).get("items", [])
                    return [self._convert_to_model(item) for item in items if self._convert_to_model(item)]
        except Exception as e:
            logger.error(f"Error querying Crossref: {e}")
        return []

    async def get_by_id(self, doi: str) -> Optional[PaperMetadata]:
        clean_doi = doi.replace("https://doi.org/", "").strip()
        url = f"{CROSSREF_BASE_URL}/{clean_doi}"
        headers = {"User-Agent": "HermesAcademicAgent/1.0 (mailto:hermes.agent@example.com)"}
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    item = res.json().get("message", {})
                    return self._convert_to_model(item)
        except Exception as e:
            logger.error(f"Error fetching Crossref DOI {doi}: {e}")
        return None

    async def get_bibtex(self, doi: str) -> Optional[str]:
        """Fetch standardized BibTeX string directly using content negotiation."""
        clean_doi = doi.replace("https://doi.org/", "").strip()
        url = f"https://doi.org/{clean_doi}"
        headers = {"Accept": "application/x-bibtex"}
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                res = await client.get(url, headers=headers)
                if res.status_code == 200:
                    return res.text
        except Exception as e:
            logger.warning(f"Failed to fetch direct BibTeX for {doi}: {e}")
        return None

    def _convert_to_model(self, item: Dict[str, Any]) -> Optional[PaperMetadata]:
        titles = item.get("title", [])
        if not titles:
            return None
        title = titles[0].strip()

        authors: List[Author] = []
        for a in item.get("author", []):
            given = a.get("given", "")
            family = a.get("family", "")
            name = f"{given} {family}".strip() or "Unknown"
            authors.append(Author(name=name))

        first_author = authors[0].name if authors else "Author"

        # Year
        year = None
        issued = item.get("issued", {}).get("date-parts", [[]])
        if issued and issued[0]:
            year = issued[0][0]

        bibtex_key = generate_bibtex_key(first_author, year, title)
        doi = item.get("DOI")

        venue = None
        containers = item.get("container-title", [])
        if containers:
            venue = containers[0]

        # Check for open access resource links
        pdf_url = None
        for link in item.get("link", []):
            if link.get("content-type") == "application/pdf":
                pdf_url = link.get("URL")
                break

        return PaperMetadata(
            bibtex_key=bibtex_key,
            title=title,
            authors=authors,
            abstract=item.get("abstract", "") or "",
            year=year,
            venue=venue or "Crossref Publisher",
            doi=doi,
            citation_count=item.get("is-referenced-by-count", 0),
            pdf_url=pdf_url,
            source="crossref",
        )
