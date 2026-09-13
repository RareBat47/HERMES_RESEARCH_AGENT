from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from src.agent.graph import ResearchBrain

router = APIRouter(prefix="/agent", tags=["agent"])
brain = ResearchBrain()


class SurveyRequest(BaseModel):
    research_question: str
    project_id: Optional[int] = None


class CompareRequest(BaseModel):
    bibtex_keys: List[str]
    criteria: List[str]


class OutlineRequest(BaseModel):
    topic: str
    bibtex_keys: List[str]


class DraftRequest(BaseModel):
    section_name: str
    topic: str
    bibtex_keys: List[str]
    project_truth: str = ""


class VerifyRequest(BaseModel):
    claim: str
    bibtex_key: str
    project_id: Optional[int] = None


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


@router.post("/outline")
async def draft_outline(req: OutlineRequest):
    notes = [{"bibtex_key": k, "title": k} for k in req.bibtex_keys]
    outline = await brain.writer.draft_outline(req.topic, notes)
    return {"outline": outline}


@router.post("/draft")
async def draft_section(req: DraftRequest):
    notes = [{"bibtex_key": k, "title": k} for k in req.bibtex_keys]
    content = await brain.writer.draft_section(
        section_name=req.section_name,
        topic=req.topic,
        notes=notes,
        project_truth=req.project_truth,
    )
    return {"section": req.section_name, "draft": content}


@router.post("/verify-claim")
async def verify_claim(req: VerifyRequest):
    result = await brain.critic.verify_claim(
        claim=req.claim,
        bibtex_key=req.bibtex_key,
        project_id=req.project_id,
    )
    return result.model_dump()
