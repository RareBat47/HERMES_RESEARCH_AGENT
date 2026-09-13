from typing import Any, Dict, List, Optional
import httpx
from src.common.logging import setup_logger
from src.common.models import Author, PaperMetadata
from src.config.settings import get_settings
from src.connectors.base import BaseConnector, generate_bibtex_key

logger = setup_logger("hermes.connectors.pubmed")

NCBI_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


class PubMedConnector(BaseConnector):
    name = "pubmed"

    def __init__(self) -> None:
        self.settings = get_settings()

    def _get_params(self) -> Dict[str, str]:
        params = {
            "email": self.settings.NCBI_EMAIL,
            "tool": "HermesResearchAgent",
        }
        if self.settings.NCBI_API_KEY:
            params["api_key"] = self.settings.NCBI_API_KEY
        return params

    async def search(self, query: str, limit: int = 5) -> List[PaperMetadata]:
        search_url = f"{NCBI_BASE_URL}/esearch.fcgi"
        params = {
            **self._get_params(),
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": limit,
            "sort": "pub_date",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.get(search_url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    id_list = data.get("esearchresult", {}).get("idlist", [])
                    if id_list:
                        return await self._fetch_summaries(client, id_list)
        except Exception as e:
            logger.error(f"Error querying PubMed: {e}")
        return []

    async def get_by_id(self, pmid: str) -> Optional[PaperMetadata]:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                papers = await self._fetch_summaries(client, [pmid])
                return papers[0] if papers else None
        except Exception as e:
            logger.error(f"Error fetching PubMed ID {pmid}: {e}")
        return None

    async def _fetch_summaries(self, client: httpx.AsyncClient, pmid_list: List[str]) -> List[PaperMetadata]:
        summary_url = f"{NCBI_BASE_URL}/esummary.fcgi"
        params = {
            **self._get_params(),
            "db": "pubmed",
            "id": ",".join(pmid_list),
            "retmode": "json",
        }
        res = await client.get(summary_url, params=params)
        if res.status_code != 200:
            return []

        data = res.json().get("result", {})
        papers: List[PaperMetadata] = []

        for pmid in pmid_list:
            item = data.get(pmid)
            if not item:
                continue

            title = item.get("title", "").strip().rstrip(".")
            if not title:
                continue

            authors = [
                Author(name=a.get("name", "Unknown"))
                for a in item.get("authors", [])
                if a.get("name")
            ]
            first_author = authors[0].name if authors else "Author"

            # Parse year from pubdate
            year = None
            pubdate = item.get("pubdate", "")
            if pubdate:
                parts = pubdate.split()
                for part in parts:
                    if part.isdigit() and len(part) == 4:
                        year = int(part)
                        break

            bibtex_key = generate_bibtex_key(first_author, year, title)

            # DOI & PMC from articleids
            doi = None
            for art_id in item.get("articleids", []):
                if art_id.get("idtype") == "doi":
                    doi = art_id.get("value")
                    break

            venue = item.get("source") or "Biomedical Journal"

            papers.append(
                PaperMetadata(
                    bibtex_key=bibtex_key,
                    title=title,
                    authors=authors,
                    abstract=item.get("sortfirstauthor", ""),
                    year=year,
                    venue=venue,
                    doi=doi,
                    pmid=pmid,
                    citation_count=0,
                    pdf_url=None,
                    source="pubmed",
                )
            )

        return papers
