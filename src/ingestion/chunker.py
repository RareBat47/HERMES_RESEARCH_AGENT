from typing import Any, Dict, List
from src.common.models import PaperSectionContent


class AcademicChunker:
    """Chunks academic paper sections into semantically cohesive passages with exact character offsets."""

    def __init__(self, target_chunk_size: int = 1200, overlap_size: int = 200) -> None:
        self.target_chunk_size = target_chunk_size
        self.overlap_size = overlap_size

    def chunk_section(
        self,
        section: PaperSectionContent,
        paper_id: int,
        bibtex_key: str,
        section_id: int = None,
    ) -> List[Dict[str, Any]]:
        """Split a paper section into chunks with exact char offsets, suitable for embedding and citation verification."""
        text = section.text_content.strip()
        if not text:
            return []

        chunks: List[Dict[str, Any]] = []

        if len(text) <= self.target_chunk_size:
            chunks.append(
                {
                    "paper_id": paper_id,
                    "section_id": section_id,
                    "bibtex_key": bibtex_key,
                    "section_name": section.section_name,
                    "heading": section.heading,
                    "text": text,
                    "text_content": text,
                    "char_start": 0,
                    "char_end": len(text),
                    "page_number": section.page_number or 1,
                    "chunk_index": 0,
                }
            )
            return chunks

        paragraphs = text.split("\n\n")
        current_chunk_parts: List[str] = []
        current_length = 0
        chunk_idx = 0
        running_char_start = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if current_length + len(para) > self.target_chunk_size and current_chunk_parts:
                chunk_str = "\n\n".join(current_chunk_parts)
                char_start_pos = text.find(chunk_str, max(0, running_char_start - 200))
                if char_start_pos == -1:
                    char_start_pos = running_char_start
                char_end_pos = char_start_pos + len(chunk_str)

                chunks.append(
                    {
                        "paper_id": paper_id,
                        "section_id": section_id,
                        "bibtex_key": bibtex_key,
                        "section_name": section.section_name,
                        "heading": section.heading,
                        "text": chunk_str,
                        "text_content": chunk_str,
                        "char_start": char_start_pos,
                        "char_end": char_end_pos,
                        "page_number": section.page_number or 1,
                        "chunk_index": chunk_idx,
                    }
                )
                chunk_idx += 1
                running_char_start = char_start_pos + len(current_chunk_parts[0])

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
            chunk_str = "\n\n".join(current_chunk_parts)
            char_start_pos = text.find(chunk_str, max(0, running_char_start - 200))
            if char_start_pos == -1:
                char_start_pos = running_char_start
            char_end_pos = char_start_pos + len(chunk_str)

            chunks.append(
                {
                    "paper_id": paper_id,
                    "section_id": section_id,
                    "bibtex_key": bibtex_key,
                    "section_name": section.section_name,
                    "heading": section.heading,
                    "text": chunk_str,
                    "text_content": chunk_str,
                    "char_start": char_start_pos,
                    "char_end": char_end_pos,
                    "page_number": section.page_number or 1,
                    "chunk_index": chunk_idx,
                }
            )

        return chunks
