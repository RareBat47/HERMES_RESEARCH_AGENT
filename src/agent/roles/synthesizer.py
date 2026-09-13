import json
from typing import Any, Dict, List
from src.agent.llm_client import LLMClient
from src.agent.state import AgentState
from src.common.logging import setup_logger

logger = setup_logger("hermes.agent.synthesizer")

SYNTHESIZER_SYSTEM_PROMPT = """You are a Principal Investigator leading a top research initiative.
Your mission is to perform cross-paper synthesis across multiple candidate works.

Analyze the papers' problems, methods, benchmarks, and limitations to produce:
1. Comparison Matrix: Key differences across methodology, assumptions, computational cost, and performance.
2. Scientific Consensus: Principles agreed upon across multiple works.
3. Disagreements / Conflicting Results: Where authors report contradictory outcomes or disputed assumptions.
4. Gaps in the Literature: Unaddressed scenarios, under-explored baselines, or missing evaluations.
5. Proposed Experiments: Concrete, actionable research experiments with ablations to resolve the gaps.

Output valid JSON matching this schema:
{
  "matrix": [
    {"bibtex_key": "...", "method": "...", "strengths": "...", "limitations": "...", "key_result": "..."}
  ],
  "consensus_points": ["point 1", "point 2"],
  "disagreements": ["dispute 1", "dispute 2"],
  "identified_gaps": ["gap 1", "gap 2"],
  "proposed_experiments": ["experiment plan 1", "experiment plan 2"]
}
"""


class SynthesizerAgent:
    """Builds cross-paper comparison matrices, isolates consensus, and highlights research gaps."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm = llm_client

    async def synthesize(self, state: AgentState) -> AgentState:
        notes = state.paper_notes or state.candidate_papers[:6]
        logger.info(f"Synthesizing across {len(notes)} literature artifacts...")

        context = f"Research Goal: {state.research_question}\n\nPapers Context:\n"
        for i, n in enumerate(notes, 1):
            key = n.get("paper_bibtex_key") or n.get("bibtex_key", f"Paper{i}")
            title = n.get("title", "")
            method = n.get("method_details") or n.get("abstract", "")
            results = n.get("results", "")
            limitations = n.get("limitations", "")
            context += f"[{key}] Title: {title}\nMethod: {method}\nResults: {results}\nLimitations: {limitations}\n\n"

        messages = [
            {"role": "system", "content": SYNTHESIZER_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ]

        try:
            content = await self.llm.chat_completion(
                messages=messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            data = json.loads(content)
            state.synthesis_matrix = data.get("matrix", [])
            state.identified_gaps = data.get("identified_gaps", [])
            state.proposed_experiments = data.get("proposed_experiments", [])
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            state.errors.append(f"Synthesizer error: {e}")

        return state
