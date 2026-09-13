import json
from typing import Any, Dict
from src.agent.llm_client import LLMClient
from src.agent.state import AgentState
from src.common.logging import setup_logger

logger = setup_logger("hermes.agent.planner")

PLANNER_SYSTEM_PROMPT = """You are the Senior Research Planner for an elite scientific lab.
Your goal is to decompose a complex scientific question into an exhaustive, structured research plan.

Given the research goal, output a strict JSON object with the following schema:
{
  "sub_questions": ["sub-question 1", "sub-question 2", ...],
  "search_queries": [
    {"source": "arxiv", "query": "..."},
    {"source": "semanticscholar", "query": "..."},
    {"source": "pubmed", "query": "..."}
  ],
  "inclusion_criteria": ["criteria 1", "criteria 2", ...],
  "exclusion_criteria": ["criteria 1", "criteria 2", ...],
  "reading_strategy": ["priority topic 1", "priority topic 2", ...]
}
Ensure search queries use effective Boolean keywords without over-constraining.
"""


class PlannerAgent:
    """Deconstructs a research objective into sub-questions, targeted queries, and inclusion criteria."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    async def plan(self, state: AgentState) -> AgentState:
        logger.info(f"Generating research plan for: {state.research_question}")
        messages = [
            {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
            {"role": "user", "content": f"Research Goal: {state.research_question}"},
        ]
        try:
            content = await self.llm.chat_completion(
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            data = json.loads(content)
            state.sub_questions = data.get("sub_questions", [])
            state.search_queries = [
                q.get("query") if isinstance(q, dict) else str(q)
                for q in data.get("search_queries", [])
            ]
            state.inclusion_criteria = data.get("inclusion_criteria", [])
            state.exclusion_criteria = data.get("exclusion_criteria", [])
            state.reading_order = data.get("reading_strategy", [])
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            state.errors.append(f"Planner error: {e}")
            # Fallback queries
            state.sub_questions = [state.research_question]
            state.search_queries = [state.research_question]

        return state
