import io
from typing import List, Optional
from bs4 import BeautifulSoup
import httpx
from src.common.exceptions import GrobidServiceError
from src.common.logging import setup_logger
from src.common.models import PaperSectionContent
from src.config.settings import get_settings

logger = setup_logger("hermes.ingestion.grobid")


class GrobidParser:
    """Communicates with GROBID service to parse PDFs into structured TEI XML sections."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.grobid_url = f"{self.settings.GROBID_URL.rstrip('/')}/api/processFulltextDocument"

    async def is_available(self) -> bool:
        """Check if GROBID service is reachable."""
        try:
            health_url = f"{self.settings.GROBID_URL.rstrip('/')}/api/isalive"
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(health_url)
                return res.status_code == 200
        except Exception:
            return False

    async def parse_pdf(self, pdf_bytes: bytes) -> List[PaperSectionContent]:
        """Send PDF bytes to GROBID and parse TEI XML response into structured sections."""
        try:
            files = {"input": ("paper.pdf", io.BytesIO(pdf_bytes), "application/pdf")}
            data = {
                "generateIDs": "1",
                "consolidateHeader": "1",
                "consolidateCitations": "0",
                "includeRawCitations": "1",
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                res = await client.post(self.grobid_url, files=files, data=data)
                if res.status_code != 200:
                    raise GrobidServiceError(f"GROBID returned status {res.status_code}: {res.text[:200]}")

                return self._parse_tei_xml(res.text)
        except Exception as e:
            logger.error(f"GROBID parsing failed: {e}")
            raise GrobidServiceError(f"GROBID processing failed: {e}") from e

    def _parse_tei_xml(self, xml_content: str) -> List[PaperSectionContent]:
        soup = BeautifulSoup(xml_content, "xml")
        sections: List[PaperSectionContent] = []

        # 1. Abstract
        abstract_elem = soup.find("abstract")
        if abstract_elem:
            abstract_text = " ".join([p.get_text(strip=True) for p in abstract_elem.find_all("p")])
            if abstract_text:
                sections.append(
                    PaperSectionContent(
                        section_name="Abstract",
                        heading="Abstract",
                        text_content=abstract_text,
                        page_number=1,
                    )
                )

        # 2. Body Divs
        body = soup.find("body")
        if body:
            divs = body.find_all("div", recursive=False)
            page_counter = 1
            for div in divs:
                head = div.find("head")
                heading_text = head.get_text(strip=True) if head else "Section"
                paragraphs = [p.get_text(strip=True) for p in div.find_all("p")]
                if not paragraphs:
                    continue

                full_text = "\n\n".join(paragraphs)
                section_type = self._classify_section_type(heading_text)

                sections.append(
                    PaperSectionContent(
                        section_name=section_type,
                        heading=heading_text,
                        text_content=full_text,
                        page_number=page_counter,
                    )
                )
                page_counter += 1

        return sections

    def _classify_section_type(self, heading: str) -> str:
        h = heading.lower()
        if "abstract" in h:
            return "Abstract"
        elif any(k in h for k in ["intro", "background", "motivation"]):
            return "Introduction"
        elif any(k in h for k in ["related", "prior work", "literature"]):
            return "Related Work"
        elif any(k in h for k in ["method", "approach", "model", "architecture", "framework", "formulation"]):
            return "Methods"
        elif any(k in h for k in ["experiment", "evaluat", "setup", "benchmark", "result", "analysis", "ablation"]):
            return "Results"
        elif any(k in h for k in ["limitat", "caveat", "broader impact"]):
            return "Limitations"
        elif any(k in h for k in ["discuss", "future work"]):
            return "Discussion"
        elif any(k in h for k in ["conclus"]):
            return "Conclusion"
        return "Body"
