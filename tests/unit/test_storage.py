import pytest
from sqlalchemy import select
from src.memory.project_memory import ProjectMemory
from src.memory.user_scratchpad import UserScratchpadManager
from src.storage.database import async_session_maker, init_db
from src.storage.models import Paper, PaperAuthor, Project


@pytest.mark.asyncio
async def test_database_initialization_and_project_memory():
    await init_db()

    async with async_session_maker() as session:
        memory = ProjectMemory(session)
        project = await memory.get_or_create_project(
            name="LLM Hallucination Reduction",
            description="Testing evidence retrieval grounding",
        )
        assert project.id is not None
        assert project.name == "LLM Hallucination Reduction"

        # Record a decision
        decision = await memory.record_decision(
            project_id=project.id,
            title="Adopt Qdrant for Passages",
            context="Evaluated Chroma vs Qdrant for production scale",
            decision="Deploy Qdrant with hybrid BM25 and dense embeddings",
            rationale="Sub-millisecond latency and high payload filtering support",
        )
        assert decision.id is not None

        # Add task
        task = await memory.add_task(project_id=project.id, title="Implement Critic verifier")
        assert task.id is not None
        assert task.status == "todo"

        # Retrieve shared truth
        truth = await memory.get_shared_truth(project.id)
        assert truth["project_name"] == "LLM Hallucination Reduction"
        assert len(truth["decisions"]) >= 1
        assert len(truth["active_tasks"]) >= 1


@pytest.mark.asyncio
async def test_user_scratchpad():
    await init_db()

    async with async_session_maker() as session:
        mgr = UserScratchpadManager(session)
        user = await mgr.get_or_create_user(discord_user_id="999888777", username="DrAlice")
        assert user.username == "DrAlice"

        content = await mgr.append_to_scratchpad(user.id, "Idea: check ablation table in Vaswani et al.")
        assert "Vaswani" in content

        pad = await mgr.get_scratchpad(user.id)
        assert "Vaswani" in pad
