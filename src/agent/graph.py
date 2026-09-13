from typing import Any, Dict, List, Optional
from src.agent.llm_client import LLMClient
from src.agent.rag_qa import GroundedQAAgent
from src.agent.roles.critic import CriticAgent
from src.agent.roles.planner import PlannerAgent
from src.agent.roles.reader import ReaderAgent
from src.agent.roles.retriever import RetrieverAgent
from src.agent.roles.synthesizer import SynthesizerAgent
from src.agent.roles.writer import WriterAgent
from src.agent.state import AgentState
from src.common.logging import setup_logger
from src.common.models import GroundedAnswer
from src.storage.vector_store import VectorStore

logger = setup_logger("hermes.agent.brain")


class ResearchBrain:
    """State graph orchestrator for the Hermes multi-agent academic brain."""

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
        self.qa = GroundedQAAgent(self.llm, self.vector_store)

    async def execute_literature_survey(self, research_question: str, project_id: Optional[int] = None) -> AgentState:
        """Sequential/conditional graph execution: Planner -> Retriever -> Reader -> Synthesizer."""
        logger.info(f"Initiating autonomous literature survey for: '{research_question}'")
        state = AgentState(research_question=research_question, project_id=project_id)

        # Node 1: Planner
        state = await self.planner.plan(state)

        # Node 2: Retriever
        state = await self.retriever.retrieve(state, limit_per_query=3)

        # Node 3: Reader / Extractor
        top_candidates = state.candidate_papers[:4]
        for paper in top_candidates:
            note = await self.reader.extract_note(
                bibtex_key=paper.get("bibtex_key", "Key"),
                title=paper.get("title", ""),
                abstract=paper.get("abstract", ""),
            )
            state.paper_notes.append(note.model_dump())

        # Node 4: Synthesizer
        state = await self.synthesizer.synthesize(state)

        return state

    async def ask_library(self, question: str, project_id: Optional[int] = None) -> GroundedAnswer:
        """Executes evidence-grounded RAG over the indexed library chunks."""
        return await self.qa.answer_question(question, project_id=project_id)
