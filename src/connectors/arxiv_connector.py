import xml.etree.ElementTree as ET
from typing import List, Optional
import httpx
from src.common.exceptions import ConnectorError
from src.common.logging import setup_logger
from src.common.models import Author, PaperMetadata
from src.connectors.base import BaseConnector, generate_bibtex_key

logger = setup_logger("hermes.connectors.arxiv")

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivConnector(BaseConnector):
    name = "arxiv"

    async def search(self, query: str, limit: int = 5) -> List[PaperMetadata]:
        headers = {"User-Agent": "HermesResearchAgent/1.0 (mailto:hermes.agent@example.com)"}
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                res = await client.get(ARXIV_API_URL, params=params, headers=headers)
                if res.status_code != 200:
                    raise ConnectorError(f"arXiv API returned status {res.status_code}")
                return self._parse_feed(res.text)
        except Exception as e:
            logger.error(f"Error querying arXiv: {e}")
            return []

    async def get_by_id(self, arxiv_id: str) -> Optional[PaperMetadata]:
        clean_id = arxiv_id.strip()
        if "/" in clean_id:
            clean_id = clean_id.split("/")[-1]
        params = {"id_list": clean_id}
        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                res = await client.get(ARXIV_API_URL, params=params)
                if res.status_code == 200:
                    papers = self._parse_feed(res.text)
                    return papers[0] if papers else None
        except Exception as e:
            logger.error(f"Error fetching arXiv paper {arxiv_id}: {e}")
        return None

    def _parse_feed(self, xml_text: str) -> List[PaperMetadata]:
        papers: List[PaperMetadata] = []
        try:
            root = ET.fromstring(xml_text)
            entries = root.findall("atom:entry", ATOM_NS)
            for entry in entries:
                # Title
                title_elem = entry.find("atom:title", ATOM_NS)
                title = " ".join(title_elem.text.strip().split()) if title_elem is not None and title_elem.text else "Untitled"

                # ID
                id_elem = entry.find("atom:id", ATOM_NS)
                arxiv_url = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                arxiv_id = arxiv_url.split("/abs/")[-1] if "/abs/" in arxiv_url else arxiv_url

                # Abstract
                summary_elem = entry.find("atom:summary", ATOM_NS)
                abstract = " ".join(summary_elem.text.strip().split()) if summary_elem is not None and summary_elem.text else ""

                # Year
                published_elem = entry.find("atom:published", ATOM_NS)
                year = None
                if published_elem is not None and published_elem.text:
                    try:
                        year = int(published_elem.text[:4])
                    except ValueError:
                        pass

                # Authors
                authors: List[Author] = []
                for author_elem in entry.findall("atom:author", ATOM_NS):
                    name_elem = author_elem.find("atom:name", ATOM_NS)
                    if name_elem is not None and name_elem.text:
                        authors.append(Author(name=name_elem.text.strip()))

                # PDF Link
                pdf_url = None
                for link in entry.findall("atom:link", ATOM_NS):
                    if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf":
                        pdf_url = link.attrib.get("href")
                        break
                if not pdf_url and arxiv_id:
                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

                # DOI
                doi_elem = entry.find("arxiv:doi", ATOM_NS)
                doi = doi_elem.text.strip() if doi_elem is not None and doi_elem.text else None

                first_author = authors[0].name if authors else "Author"
                bibtex_key = generate_bibtex_key(first_author, year, title)

                papers.append(
                    PaperMetadata(
                        bibtex_key=bibtex_key,
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        year=year,
                        venue="arXiv",
                        doi=doi,
                        arxiv_id=arxiv_id,
                        citation_count=0,
                        pdf_url=pdf_url,
                        source="arxiv",
                    )
                )
        except Exception as e:
            logger.error(f"Failed to parse arXiv Atom feed: {e}")
        return papers
