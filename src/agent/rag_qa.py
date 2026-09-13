import json
from typing import Any, Dict, List, Optional
from src.agent.llm_client import LLMClient
from src.common.logging import setup_logger
from src.common.models import CitationReference, GroundedAnswer
from src.storage.vector_store import VectorStore

logger = setup_logger("hermes.agent.rag_qa")

GROUNDED_QA_PROMPT = """You are Hermes, an academic intelligence assistant with STRICT grounding rules.
Your task is to answer the researcher's question based EXCLUSIVELY on the provided Literature Chunks from the library.

HARD CONSTRAINTS:
1. Every claim of fact, method, metric, or finding MUST be directly supported by a verbatim quote from the provided Chunks.
2. In your answer text, cite every claim using `\\cite{BibKey}`.
3. For every citation, provide the exact quote used, the BibTeX key, and the section/page hint.
4. IF THE PROVIDED CHUNKS DO NOT CONTAIN SUFFICIENT EVIDENCE TO ANSWER THE QUESTION:
   - Explicitly state that the current library does not contain sufficient grounding.
   - Set "is_grounded" to false.
   - List the unsupported claims.
   - Propose 2-3 specific search queries to retrieve the missing literature.

Output valid JSON matching this schema:
{
  "answer": "Comprehensive, evidence-grounded answer with \\cite{BibKey} citation tags...",
  "is_grounded": true | false,
  "citations": [
    {
      "bibtex_key": "AuthorYearWord",
      "exact_quote": "Verbatim quote from passage...",
      "section_hint": "Section name",
      "page_hint": 1,
      "confidence_score": 0.95
    }
  ],
  "unsupported_claims": [],
  "proposed_search_queries": ["query 1", "query 2"]
}
"""


class GroundedQAAgent:
    """Answers academic questions grounded strictly in indexed library passages with exact citation spans."""

    def __init__(self, llm_client: LLMClient, vector_store: VectorStore) -> None:
        self.llm = llm_client
        self.vector_store = vector_store

    async def answer_question(
        self,
        question: str,
        project_id: Optional[int] = None,
        top_k: int = 6,
    ) -> GroundedAnswer:
        logger.info(f"Retrieving library evidence for question: '{question}'")

        # 1. Semantic Retrieval across indexed chunks
        hits = await self.vector_store.search(
            query=question,
            limit=top_k,
            project_id=project_id,
        )

        if not hits:
            return GroundedAnswer(
                question=question,
                answer="No relevant literature chunks were found in your library for this question. Please ingest relevant papers first.",
                is_grounded=False,
                citations=[],
                unsupported_claims=[question],
                proposed_search_queries=[question, f"{question} survey"],
            )

        # 2. Format Context with explicit chunk identifiers and page/section hints
        chunks_context = ""
        for i, hit in enumerate(hits, 1):
            p = hit.get("payload", {})
            bib_key = p.get("bibtex_key", "UnknownKey")
            sec_name = p.get("section_name", "Section")
            heading = p.get("heading", "")
            page = p.get("page_number", 1)
            chunk_text = p.get("text_content", "")
            chunks_context += f"--- CHUNK {i} [{bib_key} | {sec_name}: {heading} | Page {page}] ---\n{chunk_text}\n\n"

        prompt = f"Researcher Question: {question}\n\nLiterature Chunks from Library:\n{chunks_context}"
        messages = [
            {"role": "system", "content": GROUNDED_QA_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            raw_response = await self.llm.chat_completion(
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            data = json.loads(raw_response)

            citations = [
                CitationReference(
                    bibtex_key=c.get("bibtex_key", "Key"),
                    exact_quote=c.get("exact_quote", ""),
                    section_hint=c.get("section_hint"),
                    page_hint=c.get("page_hint"),
                    confidence_score=float(c.get("confidence_score", 1.0)),
                )
                for c in data.get("citations", [])
            ]

            return GroundedAnswer(
                question=question,
                answer=data.get("answer", "No answer generated."),
                is_grounded=data.get("is_grounded", True),
                citations=citations,
                unsupported_claims=data.get("unsupported_claims", []),
                proposed_search_queries=data.get("proposed_search_queries", []),
            )
        except Exception as e:
            logger.error(f"Grounded QA failed: {e}")
            return GroundedAnswer(
                question=question,
                answer=f"An error occurred while evaluating library evidence: {e}",
                is_grounded=False,
                citations=[],
                unsupported_claims=[question],
                proposed_search_queries=[question],
            )
