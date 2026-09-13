import json
import re
from typing import List, Optional
from src.agent.cohere_client import CohereClient
from src.common.logging import setup_logger
from src.common.models import CitationVerificationResult
from src.storage.vector_store import VectorStore

logger = setup_logger("hermes.agent.critic")

CRITIC_PROMPT = """You are an exacting Academic Fact-Checker and Citation Verifier.
Evaluate whether the following Grounding Passage from the paper genuinely and directly supports the Author's Claim.

Author Claim:
\"{claim}\"

Cited Paper Passage:
\"{passage}\"

Output valid JSON:
{{
  "is_verified": true | false,
  "confidence_score": 0.0 to 1.0,
  "critique": "Brief explanation of whether the passage supports the claim or if it is unsupported/exaggerated"
}}
"""


class CriticAgent:
    """Rigorous citation verification and claim-grounding inspector."""

    def __init__(self, cohere_client: CohereClient, vector_store: Optional[VectorStore] = None) -> None:
        self.cohere = cohere_client
        self.vector_store = vector_store or VectorStore()

    async def verify_claim(
        self,
        claim: str,
        bibtex_key: str,
        project_id: Optional[int] = None,
    ) -> CitationVerificationResult:
        logger.info(f"Verifying claim against {bibtex_key}: {claim[:80]}...")

        # Search the vector store specifically for chunks belonging to this paper
        hits = await self.vector_store.search(
            query=claim,
            limit=3,
            bibtex_key=bibtex_key,
            project_id=project_id,
        )

        if not hits:
            return CitationVerificationResult(
                claim=claim,
                bibtex_key=bibtex_key,
                grounding_passage="No indexed passages found for this paper.",
                similarity_score=0.0,
                is_verified=False,
                critique="The paper is either not indexed in the vector database or does not contain text matching this claim.",
            )

        best_passage = hits[0]["payload"].get("text_content", "")
        best_score = float(hits[0].get("score", 0.0))

        prompt = CRITIC_PROMPT.format(claim=claim, passage=best_passage[:3000])
        messages = [
            {"role": "system", "content": "You are a scientific citation verifier."},
            {"role": "user", "content": prompt},
        ]

        try:
            content = await self.cohere.chat_completion(
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            data = json.loads(content)
            return CitationVerificationResult(
                claim=claim,
                bibtex_key=bibtex_key,
                grounding_passage=best_passage,
                similarity_score=best_score,
                confidence_score=float(data.get("confidence_score", best_score)),
                is_verified=data.get("is_verified", False),
                critique=data.get("critique", "Verification completed."),
            )
        except Exception as e:
            logger.error(f"Citation verification error: {e}")
            return CitationVerificationResult(
                claim=claim,
                bibtex_key=bibtex_key,
                grounding_passage=best_passage,
                similarity_score=best_score,
                confidence_score=best_score,
                is_verified=True if best_score > 0.75 else False,
                critique=f"Heuristic verification fallback due to: {e}",
            )
