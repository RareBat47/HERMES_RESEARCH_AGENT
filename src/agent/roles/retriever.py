import asyncio
import re
from typing import Dict, List, Optional
from src.agent.state import AgentState
from src.common.logging import setup_logger
from src.common.models import PaperMetadata
from src.connectors.arxiv_connector import ArxivConnector
from src.connectors.crossref_connector import CrossrefConnector
from src.connectors.pubmed_connector import PubMedConnector
from src.connectors.semantic_scholar import SemanticScholarConnector

logger = setup_logger("hermes.agent.retriever")


def normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


class RetrieverAgent:
    """Multi-source literature retrieval, cross-engine deduplication, and ranking."""

    def __init__(self) -> None:
        self.arxiv = ArxivConnector()
        self.s2 = SemanticScholarConnector()
        self.pubmed = PubMedConnector()
        self.crossref = CrossrefConnector()

    async def retrieve(self, state: AgentState, limit_per_query: int = 4) -> AgentState:
        queries = state.search_queries or [state.research_question]
        logger.info(f"Retrieving literature across {len(queries)} query permutations...")

        tasks = []
        for q in queries:
            tasks.append(self.arxiv.search(q, limit=limit_per_query))
            tasks.append(self.s2.search(q, limit=limit_per_query))
            tasks.append(self.pubmed.search(q, limit=limit_per_query))

        results_lists = await asyncio.gather(*tasks, return_exceptions=True)

        all_papers: List[PaperMetadata] = []
        for res in results_lists:
            if isinstance(res, list):
                all_papers.extend(res)

        # Deduplication by DOI and normalized title
        seen_dois = set()
        seen_titles = set()
        deduped: List[PaperMetadata] = []

        for p in all_papers:
            norm_t = normalize_title(p.title)
            if p.doi and p.doi.lower() in seen_dois:
                continue
            if norm_t in seen_titles:
                continue

            if p.doi:
                seen_dois.add(p.doi.lower())
            seen_titles.add(norm_t)
            deduped.append(p)

        # Rank by citation count and recency
        deduped.sort(
            key=lambda x: ((x.year or 2000) * 10 + min(x.citation_count, 500)),
            reverse=True,
        )

        state.candidate_papers = [p.model_dump() for p in deduped]
        logger.info(f"Retrieved {len(all_papers)} papers -> {len(deduped)} deduplicated candidates.")
        return state
