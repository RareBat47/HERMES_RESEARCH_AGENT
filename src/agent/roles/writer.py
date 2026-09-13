from typing import Any, Dict, List
from src.agent.cohere_client import CohereClient
from src.agent.state import AgentState
from src.common.logging import setup_logger

logger = setup_logger("hermes.agent.writer")

WRITER_SYSTEM_PROMPT = """You are an academic author drafting a peer-reviewed research manuscript.
Rules for drafting:
1. Maintain formal academic tone, rigorous scientific framing, and clear structural hierarchy.
2. CITATION REQUIREMENT: Every claim of fact, prior method, or baseline result MUST be explicitly cited using the exact BibTeX keys provided in the context. Format citations as `\\cite{BibKey}` or `[@BibKey]`.
3. Do NOT cite fictitious keys. Use ONLY the keys present in the provided notes.
"""


class WriterAgent:
    """Drafts comprehensive academic paper outlines and section drafts backed by BibTeX keys using Cohere."""

    def __init__(self, cohere_client: CohereClient) -> None:
        self.cohere = cohere_client

    async def draft_outline(self, topic: str, notes: List[Dict[str, Any]]) -> str:
        keys_summary = "\n".join([f"- {n.get('bibtex_key', 'Key')}: {n.get('title', '')}" for n in notes])
        prompt = f"Topic: {topic}\n\nAvailable Citations:\n{keys_summary}\n\nGenerate an exhaustive academic paper outline with section breakdown, bulleted narrative flow, and recommended citation placements."

        return await self.cohere.chat(
            message=prompt,
            system_prompt=WRITER_SYSTEM_PROMPT,
            temperature=0.2,
        )

    async def draft_section(
        self,
        section_name: str,
        topic: str,
        notes: List[Dict[str, Any]],
        project_truth: str = "",
    ) -> str:
        bibtex_context = ""
        for n in notes:
            key = n.get("bibtex_key") or n.get("paper_bibtex_key", "Key")
            title = n.get("title", "")
            method = n.get("method_details") or n.get("key_idea", "")
            results = n.get("results", "")
            bibtex_context += f"\\bibitem{{{key}}} {title}. Details: {method}. Findings: {results}\n"

        prompt = f"""Draft Section: {section_name}
Target Research Topic: {topic}

Shared Project Decisions / Truth:
{project_truth or 'Standard academic investigation'}

Available Literature & Keys:
{bibtex_context}

Write a full academic draft for this section. Ground all comparative statements directly in the literature keys above.
"""
        return await self.cohere.chat(
            message=prompt,
            system_prompt=WRITER_SYSTEM_PROMPT,
            temperature=0.2,
        )
