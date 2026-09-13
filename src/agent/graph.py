from typing import Any, Dict, List, Optional
from sqlalchemy import select
from src.agent.cohere_client import CohereClient
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
from src.gap_finder.analyzer import ResearchGapAnalyzer
from src.storage.database import async_session_maker
from src.storage.models import Paper, PaperNote, Project
from src.storage.vector_store import VectorStore

logger = setup_logger("hermes.agent.brain")


class ResearchBrain:
    """State graph orchestrator for the Hermes multi-agent academic brain."""

    def __init__(
        self,
        cohere_client: Optional[CohereClient] = None,
        vector_store: Optional[VectorStore] = None,
    ) -> None:
        self.cohere = cohere_client or CohereClient()
        self.llm = self.cohere
        self.vector_store = vector_store or VectorStore(cohere_client=self.cohere)

        self.planner = PlannerAgent(self.cohere)
        self.retriever = RetrieverAgent()
        self.reader = ReaderAgent(self.cohere)
        self.synthesizer = SynthesizerAgent(self.cohere)
        self.writer = WriterAgent(self.cohere)
        self.critic = CriticAgent(self.cohere, self.vector_store)
        self.qa = GroundedQAAgent(self.cohere, self.vector_store)
        self.gap_finder = ResearchGapAnalyzer(self.cohere)

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

    async def analyze_project_gaps(
        self,
        project_id: Optional[int] = None,
        papers: Optional[List[Dict[str, Any]]] = None,
        project_goal: str = "",
    ) -> Dict[str, Any]:
        """Runs open-source gap analysis over project literature or provided papers."""
        if papers is not None:
            return await self.gap_finder.analyze_gaps(papers, project_goal=project_goal)

        # Query database for papers and notes
        fetched_papers: List[Dict[str, Any]] = []
        try:
            async with async_session_maker() as session:
                if project_id and not project_goal:
                    proj_res = await session.execute(select(Project).where(Project.id == project_id))
                    proj = proj_res.scalar_one_or_none()
                    if proj:
                        project_goal = proj.research_goal or proj.name

                stmt = select(Paper)
                res = await session.execute(stmt)
                db_papers = res.scalars().all()

                for p in db_papers:
                    p_dict: Dict[str, Any] = {
                        "bibtex_key": p.bibtex_key,
                        "title": p.title,
                        "abstract": p.abstract or "",
                        "year": p.year or 2024,
                        "venue": p.venue or "",
                        "doi": p.doi,
                        "notes": [],
                    }
                    if p.notes:
                        for n in p.notes:
                            if not project_id or n.project_id == project_id:
                                p_dict["notes"].append({
                                    "datasets": n.datasets or [],
                                    "metrics": n.metrics or [],
                                    "limitations": n.limitations or "",
                                    "method_details": n.method_details or "",
                                })
                    fetched_papers.append(p_dict)
        except Exception as e:
            logger.warning(f"Failed to query database for papers during gap analysis: {e}")

        return await self.gap_finder.analyze_gaps(fetched_papers, project_goal=project_goal)
