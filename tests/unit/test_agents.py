import pytest
from unittest.mock import AsyncMock, MagicMock
from src.agent.cohere_client import CohereClient
from src.agent.roles.critic import CriticAgent
from src.agent.roles.planner import PlannerAgent
from src.agent.roles.writer import WriterAgent
from src.agent.state import AgentState
from src.storage.vector_store import VectorStore


@pytest.mark.asyncio
async def test_planner_agent():
    mock_cohere = MagicMock(spec=CohereClient)
    ret_val = """{
        "sub_questions": ["What is hallucination in LLMs?", "How to ground with passages?"],
        "search_queries": ["hallucination mitigation", "citation grounding"],
        "inclusion_criteria": ["empirical benchmarks", "after 2022"],
        "exclusion_criteria": ["surveys only"],
        "reading_strategy": ["Foundational theory first"]
    }"""
    mock_cohere.chat = AsyncMock(return_value=ret_val)
    mock_cohere.chat_completion = AsyncMock(return_value=ret_val)

    planner = PlannerAgent(mock_cohere)
    state = AgentState(research_question="How can we prevent LLM hallucinations?")
    new_state = await planner.plan(state)

    assert len(new_state.sub_questions) == 2
    assert len(new_state.search_queries) == 2
    assert "empirical benchmarks" in new_state.inclusion_criteria


@pytest.mark.asyncio
async def test_critic_citation_verifier():
    mock_cohere = MagicMock(spec=CohereClient)
    ret_val = """{
        "is_verified": true,
        "confidence_score": 0.95,
        "critique": "The quoted passage directly states that self-attention reduces computational complexity per layer."
    }"""
    mock_cohere.chat = AsyncMock(return_value=ret_val)
    mock_cohere.chat_completion = AsyncMock(return_value=ret_val)

    mock_vector_store = MagicMock(spec=VectorStore)
    mock_vector_store.search = AsyncMock(
        return_value=[
            {
                "score": 0.92,
                "payload": {
                    "text_content": "Self-attention layers connect all positions with a constant number of sequentially executed operations.",
                    "bibtex_key": "Vaswani2017Attention",
                    "section_name": "Methods",
                },
            }
        ]
    )

    critic = CriticAgent(mock_cohere, mock_vector_store)
    result = await critic.verify_claim(
        claim="Self-attention allows constant number of sequentially executed operations.",
        bibtex_key="Vaswani2017Attention",
    )

    assert result.is_verified is True
    assert result.confidence_score == 0.95
    assert "Self-attention" in result.grounding_passage


@pytest.mark.asyncio
async def test_writer_agent():
    mock_cohere = MagicMock(spec=CohereClient)
    ret_val = "In recent work, \\cite{Vaswani2017Attention} proposed the Transformer architecture."
    mock_cohere.chat = AsyncMock(return_value=ret_val)
    mock_cohere.chat_completion = AsyncMock(return_value=ret_val)

    writer = WriterAgent(mock_cohere)
    draft = await writer.draft_section(
        section_name="Related Work",
        topic="Transformers",
        notes=[{"bibtex_key": "Vaswani2017Attention", "title": "Attention Is All You Need"}],
    )

    assert "\\cite{Vaswani2017Attention}" in draft
