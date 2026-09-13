from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentState(BaseModel):
    """Execution state passed through the Hermes Multi-Agent Brain."""

    research_question: str
    project_id: Optional[int] = None
    sub_questions: List[str] = Field(default_factory=list)
    search_queries: List[str] = Field(default_factory=list)
    inclusion_criteria: List[str] = Field(default_factory=list)
    exclusion_criteria: List[str] = Field(default_factory=list)
    reading_order: List[str] = Field(default_factory=list)

    # Literature & Notes
    candidate_papers: List[Dict[str, Any]] = Field(default_factory=list)
    selected_papers: List[Dict[str, Any]] = Field(default_factory=list)
    paper_notes: List[Dict[str, Any]] = Field(default_factory=list)

    # Synthesis & Hypotheses
    synthesis_matrix: Dict[str, Any] = Field(default_factory=dict)
    identified_gaps: List[str] = Field(default_factory=list)
    proposed_experiments: List[str] = Field(default_factory=list)

    # Writing & Citations
    outline: Dict[str, Any] = Field(default_factory=dict)
    draft_sections: Dict[str, str] = Field(default_factory=dict)
    citation_verifications: List[Dict[str, Any]] = Field(default_factory=list)

    # Diagnostics
    errors: List[str] = Field(default_factory=list)
