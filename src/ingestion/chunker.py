from typing import Any, Dict, List
from src.common.models import PaperSectionContent


class AcademicChunker:
    """Chunks academic paper sections into semantically cohesive passages while preserving hierarchy."""

    def __init__(self, target_chunk_size: int = 1200, overlap_size: int = 200) -> None:
        self.target_chunk_size = target_chunk_size
        self.overlap_size = overlap_size

    def chunk_section(
        self,
        section: PaperSectionContent,
        paper_id: int,
        bibtex_key: str,
    ) -> List[Dict[str, Any]]:
        """Split a paper section into chunks suitable for embedding and citation verification."""
        text = section.text_content.strip()
        if not text:
            return []

        chunks: List[Dict[str, Any]] = []

        # If text is already under chunk size, keep as single chunk
        if len(text) <= self.target_chunk_size:
            chunks.append(
                {
                    "paper_id": paper_id,
                    "bibtex_key": bibtex_key,
                    "section_name": section.section_name,
                    "heading": section.heading,
                    "text_content": text,
                    "page_number": section.page_number,
                    "chunk_index": 0,
                }
            )
            return chunks

        # Sliding window with paragraph boundaries
        paragraphs = text.split("\n\n")
        current_chunk_parts: List[str] = []
        current_length = 0
        chunk_idx = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if current_length + len(para) > self.target_chunk_size and current_chunk_parts:
                chunk_str = "\n\n".join(current_chunk_parts)
                chunks.append(
                    {
                        "paper_id": paper_id,
                        "bibtex_key": bibtex_key,
                        "section_name": section.section_name,
                        "heading": section.heading,
                        "text_content": chunk_str,
                        "page_number": section.page_number,
                        "chunk_index": chunk_idx,
                    }
                )
                chunk_idx += 1
                # Overlap: keep last paragraph if reasonable size
                if len(current_chunk_parts[-1]) < self.overlap_size:
                    current_chunk_parts = [current_chunk_parts[-1], para]
                    current_length = sum(len(p) for p in current_chunk_parts)
                else:
                    current_chunk_parts = [para]
                    current_length = len(para)
            else:
                current_chunk_parts.append(para)
                current_length += len(para)

        if current_chunk_parts:
            chunks.append(
                {
                    "paper_id": paper_id,
                    "bibtex_key": bibtex_key,
                    "section_name": section.section_name,
                    "heading": section.heading,
                    "text_content": "\n\n".join(current_chunk_parts),
                    "page_number": section.page_number,
                    "chunk_index": chunk_idx,
                }
            )

        return chunks
