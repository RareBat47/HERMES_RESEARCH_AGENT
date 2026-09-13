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


@pytest.mark.asyncio
async def test_paper_chunk_and_ingestion_job():
    import uuid
    from src.storage.models import IngestionJob, Paper, PaperChunk, PaperSection
    await init_db()

    unique_key = f"TestVaswani2017_{uuid.uuid4().hex[:6]}"

    async with async_session_maker() as session:
        # 1. Test IngestionJob
        job = IngestionJob(identifier="1706.03762", status="parsing", progress=50)
        session.add(job)
        await session.flush()
        assert job.id is not None
        assert job.progress == 50

        # 2. Test Paper and PaperChunk
        paper = Paper(
            bibtex_key=unique_key,
            title="Attention Is All You Need",
            abstract="Transformer architecture test",
            parse_status="parsed",
            index_status="indexed",
        )
        session.add(paper)
        await session.flush()

        section = PaperSection(
            paper_id=paper.id,
            section_name="Methods",
            heading="3. Architecture",
            text_content="Transformer model details",
            page_number=3,
        )
        session.add(section)
        await session.flush()

        mock_point_id = f"mock-qdrant-{uuid.uuid4().hex[:8]}"
        chunk = PaperChunk(
            paper_id=paper.id,
            section_id=section.id,
            chunk_index=0,
            text="Transformer model details",
            char_start=0,
            char_end=24,
            page_number=3,
            qdrant_point_id=mock_point_id,
            embedding_model="text-embedding-3-small",
        )
        session.add(chunk)
        await session.commit()

        # Query chunk
        stmt = select(PaperChunk).where(PaperChunk.qdrant_point_id == mock_point_id)
        res = await session.execute(stmt)
        saved_chunk = res.scalar_one_or_none()
        assert saved_chunk is not None
        assert saved_chunk.char_end == 24
        assert saved_chunk.paper_id == paper.id

