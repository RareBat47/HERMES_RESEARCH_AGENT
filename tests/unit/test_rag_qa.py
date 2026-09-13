import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agent.llm_client import LLMClient
from src.agent.rag_qa import GroundedQAAgent
from src.storage.vector_store import VectorStore


@pytest.mark.asyncio
async def test_grounded_qa_with_evidence():
    mock_llm = MagicMock(spec=LLMClient)
    mock_llm.chat_completion = AsyncMock(
        return_value="""{
            "answer": "Self-attention reduces sequential operations to O(1) \\\\cite{Vaswani2017Attention}.",
            "is_grounded": true,
            "citations": [
                {
                    "bibtex_key": "Vaswani2017Attention",
                    "exact_quote": "Self-attention connects all positions with a constant number of sequentially executed operations.",
                    "section_hint": "Introduction",
                    "page_hint": 2,
                    "confidence_score": 0.98
                }
            ],
            "unsupported_claims": [],
            "proposed_search_queries": []
        }"""
    )

    mock_vector = MagicMock(spec=VectorStore)
    mock_vector.search = AsyncMock(
        return_value=[
            {
                "score": 0.95,
                "payload": {
                    "bibtex_key": "Vaswani2017Attention",
                    "section_name": "Introduction",
                    "heading": "1. Introduction",
                    "page_number": 2,
                    "text_content": "Self-attention connects all positions with a constant number of sequentially executed operations.",
                },
            }
        ]
    )

    qa = GroundedQAAgent(mock_llm, mock_vector)
    result = await qa.answer_question("How does self-attention affect sequential operations?")

    assert result.is_grounded is True
    assert len(result.citations) == 1
    assert result.citations[0].bibtex_key == "Vaswani2017Attention"
    assert result.citations[0].page_hint == 2
    assert "constant number" in result.citations[0].exact_quote


@pytest.mark.asyncio
async def test_grounded_qa_no_evidence_proposes_searches():
    mock_llm = MagicMock(spec=LLMClient)
    mock_vector = MagicMock(spec=VectorStore)
    mock_vector.search = AsyncMock(return_value=[])  # Empty library

    qa = GroundedQAAgent(mock_llm, mock_vector)
    result = await qa.answer_question("What is the quantum teleportation fidelity of system X?")

    assert result.is_grounded is False
    assert len(result.citations) == 0
    assert len(result.proposed_search_queries) >= 1
    assert "quantum teleportation" in result.proposed_search_queries[0].lower()
