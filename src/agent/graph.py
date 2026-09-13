from typing import Optional
from src.agent.llm_client import LLMClient
from src.agent.roles.critic import CriticAgent
from src.agent.roles.planner import PlannerAgent
from src.agent.roles.reader import ReaderAgent
from src.agent.roles.retriever import RetrieverAgent
from src.agent.roles.synthesizer import SynthesizerAgent
from src.agent.roles.writer import WriterAgent
from src.agent.state import AgentState
from src.common.logging import setup_logger
from src.storage.vector_store import VectorStore

logger = setup_logger("hermes.agent.brain")


class ResearchBrain:
    """Orchestrator for the Hermes multi-agent academic brain."""

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        vector_store: Optional[VectorStore] = None,
    ) -> None:
        self.llm = llm_client or LLMClient()
        self.vector_store = vector_store or VectorStore()

        self.planner = PlannerAgent(self.llm)
        self.retriever = RetrieverAgent()
        self.reader = ReaderAgent(self.llm)
        self.synthesizer = SynthesizerAgent(self.llm)
        self.writer = WriterAgent(self.llm)
        self.critic = CriticAgent(self.llm, self.vector_store)

    async def execute_literature_survey(self, research_question: str, project_id: Optional[int] = None) -> AgentState:
        """Executes full autonomous pipeline: Plan -> Retrieve -> Extract Notes -> Synthesize Matrix."""
        logger.info(f"Initiating autonomous literature survey: '{research_question}'")
        state = AgentState(research_question=research_question, project_id=project_id)

        # 1. Planning
        state = await self.planner.plan(state)

        # 2. Retrieval
        state = await self.retriever.retrieve(state, limit_per_query=3)

        # 3. Reading & Structured Extraction for top retrieved papers
        top_candidates = state.candidate_papers[:4]
        for paper in top_candidates:
            note = await self.reader.extract_note(
                bibtex_key=paper.get("bibtex_key", "Key"),
                title=paper.get("title", ""),
                abstract=paper.get("abstract", ""),
            )
            state.paper_notes.append(note.model_dump())

        # 4. Cross-Paper Synthesis
        state = await self.synthesizer.synthesize(state)

        return state
