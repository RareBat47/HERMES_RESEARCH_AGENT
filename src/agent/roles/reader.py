import json
from typing import Any, Dict, List
from src.agent.llm_client import LLMClient
from src.agent.state import AgentState
from src.common.logging import setup_logger
from src.common.models import StructuredPaperNote

logger = setup_logger("hermes.agent.reader")

READER_SYSTEM_PROMPT = """You are a Principal Scientific Reviewer for top conferences (NeurIPS/ICLR/Nature).
Your task is to extract a deep, rigorous, structured note from the provided scientific paper.

Return a valid JSON object strictly matching this schema:
{
  "problem": "Precise research challenge addressed",
  "key_idea": "Core conceptual or algorithmic novelty",
  "method_details": "In-depth mathematical, architectural, or procedural breakdown",
  "datasets": ["dataset 1", "dataset 2"],
  "metrics": ["metric 1", "metric 2"],
  "results": "Concrete numerical/empirical improvements vs baselines",
  "limitations": "Explicit assumptions, compute bottlenecks, or failure modes",
  "reproducibility_notes": "Code repository, hyperparameters, seeds, hardware reported",
  "important_quotes": [
    {"quote": "Verbatim quote", "section": "Section name", "page": 1}
  ]
}
Be precise, academic, and avoid superficial summaries.
"""


class ReaderAgent:
    """Extracts structured scientific contributions, empirical results, and exact quotes."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    async def extract_note(
        self,
        bibtex_key: str,
        title: str,
        abstract: str,
        sections_text: str = "",
    ) -> StructuredPaperNote:
        logger.info(f"Extracting structured note for paper: {bibtex_key}")

        content_input = f"Title: {title}\n\nAbstract:\n{abstract}\n\n"
        if sections_text:
            content_input += f"Extracted Sections:\n{sections_text[:14000]}"

        messages = [
            {"role": "system", "content": READER_SYSTEM_PROMPT},
            {"role": "user", "content": content_input},
        ]

        try:
            raw_response = await self.llm.chat_completion(
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            data = json.loads(raw_response)
            data["paper_bibtex_key"] = bibtex_key
            return StructuredPaperNote(**data)
        except Exception as e:
            logger.error(f"Reader extraction failed for {bibtex_key}: {e}")
            return StructuredPaperNote(
                paper_bibtex_key=bibtex_key,
                problem="Extraction error or fallback",
                key_idea=abstract[:200] if abstract else "N/A",
                method_details="N/A",
                datasets=[],
                metrics=[],
                results="N/A",
                limitations="N/A",
                reproducibility_notes="N/A",
                important_quotes=[],
            )
