from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from src.agent.graph import ResearchBrain
from src.common.models import GroundedAnswer

router = APIRouter(prefix="/agent", tags=["agent"])
brain = ResearchBrain()


class AskRequest(BaseModel):
    question: str
    project_id: Optional[int] = None
    scope: str = Field(default="library", description="library or web")


class SurveyRequest(BaseModel):
    research_question: str
    project_id: Optional[int] = None


class CompareRequest(BaseModel):
    paper_keys: List[str]
    criteria: Optional[List[str]] = Field(default_factory=lambda: ["methods", "results", "limitations"])


class OutlineRequest(BaseModel):
    topic: str
    target: Optional[str] = "full_paper"  # related work, methodology, or full paper
    bibtex_keys: Optional[List[str]] = Field(default_factory=list)


class DraftRequest(BaseModel):
    section: str
    project_id: Optional[int] = None
    topic: Optional[str] = ""
    bibtex_keys: Optional[List[str]] = Field(default_factory=list)


class VerifyRequest(BaseModel):
    claim: str
    bibtex_key: str
    project_id: Optional[int] = None


@router.post("/ask", response_model=GroundedAnswer)
async def ask_library(req: AskRequest):
    """Answers academic questions strictly grounded in indexed library chunks with exact citation spans."""
    try:
        grounded_answer = await brain.ask_library(
            question=req.question,
            project_id=req.project_id,
        )
        return grounded_answer
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/survey")
async def run_literature_survey(req: SurveyRequest):
    try:
        state = await brain.execute_literature_survey(req.research_question, req.project_id)
        return {
            "research_question": state.research_question,
            "sub_questions": state.sub_questions,
            "search_queries": state.search_queries,
            "candidate_papers": len(state.candidate_papers),
            "paper_notes": state.paper_notes,
            "synthesis_matrix": state.synthesis_matrix,
            "identified_gaps": state.identified_gaps,
            "proposed_experiments": state.proposed_experiments,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare")
async def compare_papers(req: CompareRequest):
    try:
        from src.agent.state import AgentState
        mock_notes = [{"bibtex_key": k, "title": k, "method_details": "Literature item", "results": "Benchmarked"} for k in req.paper_keys]
        state = AgentState(research_question=f"Compare {', '.join(req.paper_keys)}")
        state.paper_notes = mock_notes
        state = await brain.synthesizer.synthesize(state)
        return {
            "papers": req.paper_keys,
            "matrix": state.synthesis_matrix,
            "identified_gaps": state.identified_gaps,
            "proposed_experiments": state.proposed_experiments,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/outline")
async def draft_outline(req: OutlineRequest):
    notes = [{"bibtex_key": k, "title": k} for k in req.bibtex_keys]
    target_prompt = f"{req.topic} (Target Focus: {req.target})"
    outline = await brain.writer.draft_outline(target_prompt, notes)
    return {"topic": req.topic, "target": req.target, "outline": outline}


@router.post("/draft")
async def draft_section(req: DraftRequest):
    notes = [{"bibtex_key": k, "title": k} for k in req.bibtex_keys]
    content = await brain.writer.draft_section(
        section_name=req.section,
        topic=req.topic or req.section,
        notes=notes,
        project_truth=f"Project {req.project_id} investigation",
    )
    return {"section": req.section, "project_id": req.project_id, "draft": content}


@router.post("/verify-claim")
async def verify_claim(req: VerifyRequest):
    result = await brain.critic.verify_claim(
        claim=req.claim,
        bibtex_key=req.bibtex_key,
        project_id=req.project_id,
    )
    return result.model_dump()
