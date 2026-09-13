import re
from typing import List
import fitz  # PyMuPDF
from src.common.logging import setup_logger
from src.common.models import PaperSectionContent

logger = setup_logger("hermes.ingestion.pymupdf")

HEADER_PATTERN = re.compile(
    r"^(?:[0-9IVXLCDM]+\.?\s+)?(Abstract|Introduction|Related\s+Work|Background|Methods?|Methodology|Model|Proposed\s+Method|Experiments?|Results?|Discussion|Conclusions?|Limitations?|References?)\b",
    re.IGNORECASE,
)


class PyMuPDFParser:
    """Fallback scientific PDF parser using PyMuPDF (fitz) with heuristic section detection."""

    def parse_pdf(self, pdf_bytes: bytes) -> List[PaperSectionContent]:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        sections: List[PaperSectionContent] = []

        current_heading = "Introduction"
        current_section_type = "Introduction"
        current_text_blocks: List[str] = []
        current_page = 1

        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text")
            lines = text.split("\n")

            for line in lines:
                clean_line = line.strip()
                if not clean_line:
                    continue

                match = HEADER_PATTERN.match(clean_line)
                if match and len(clean_line) < 80:
                    # Flush accumulated section text
                    if current_text_blocks:
                        sections.append(
                            PaperSectionContent(
                                section_name=current_section_type,
                                heading=current_heading,
                                text_content="\n\n".join(current_text_blocks),
                                page_number=current_page,
                            )
                        )
                        current_text_blocks = []

                    raw_header = match.group(1).capitalize()
                    current_heading = clean_line
                    current_section_type = self._normalize_section_type(raw_header)
                    current_page = page_num
                else:
                    current_text_blocks.append(clean_line)

        # Flush final section
        if current_text_blocks:
            sections.append(
                PaperSectionContent(
                    section_name=current_section_type,
                    heading=current_heading,
                    text_content="\n\n".join(current_text_blocks),
                    page_number=current_page,
                )
            )

        doc.close()

        # If heuristic split yielded no divisions, return single body block
        if not sections:
            doc_all = fitz.open(stream=pdf_bytes, filetype="pdf")
            all_text = "\n\n".join([p.get_text("text") for p in doc_all])
            doc_all.close()
            sections.append(
                PaperSectionContent(
                    section_name="Body",
                    heading="Full Paper Content",
                    text_content=all_text,
                    page_number=1,
                )
            )

        return sections

    def _normalize_section_type(self, raw_header: str) -> str:
        h = raw_header.lower()
        if "abstract" in h:
            return "Abstract"
        elif "intro" in h or "background" in h:
            return "Introduction"
        elif "related" in h:
            return "Related Work"
        elif "method" in h or "model" in h:
            return "Methods"
        elif "experiment" in h or "result" in h:
            return "Results"
        elif "limitat" in h:
            return "Limitations"
        elif "discuss" in h:
            return "Discussion"
        elif "conclus" in h:
            return "Conclusion"
        return "Body"
