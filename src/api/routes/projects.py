from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.memory.project_memory import ProjectMemory
from src.memory.user_scratchpad import UserScratchpadManager
from src.storage.database import get_db
from src.storage.models import Project, User

router = APIRouter(prefix="/projects", tags=["projects"])


class CreateProjectRequest(BaseModel):
    name: str
    research_goal: Optional[str] = None
    inclusion_criteria: Optional[List[str]] = None
    exclusion_criteria: Optional[List[str]] = None


class DecisionRequest(BaseModel):
    title: str
    context: str
    decision: str
    rationale: str
    user_id: Optional[int] = None


class TaskRequest(BaseModel):
    title: str
    user_id: Optional[int] = None


class ScratchpadRequest(BaseModel):
    note: str
    project_id: Optional[int] = None


@router.post("", response_model=dict)
@router.post("/create", response_model=dict)
async def create_project(
    req: CreateProjectRequest,
    db: AsyncSession = Depends(get_db),
):
    mem = ProjectMemory(db)
    proj = await mem.get_or_create_project(req.name, req.research_goal)
    if req.inclusion_criteria:
        proj.inclusion_criteria = {"criteria": req.inclusion_criteria}
    if req.exclusion_criteria:
        proj.exclusion_criteria = {"criteria": req.exclusion_criteria}
    await db.commit()
    await db.refresh(proj)
    return {
        "id": proj.id,
        "name": proj.name,
        "research_goal": proj.research_goal,
        "is_active": proj.is_active,
    }


@router.get("", response_model=List[dict])
async def list_projects(db: AsyncSession = Depends(get_db)):
    stmt = select(Project).order_by(Project.created_at.desc())
    res = await db.execute(stmt)
    projects = res.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "research_goal": p.research_goal,
            "is_active": p.is_active,
        }
        for p in projects
    ]


@router.post("/{project_id}/switch")
async def switch_project(
    project_id: int,
    discord_user_id: str = Query(..., description="Discord user ID switching project"),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(User).where(User.discord_user_id == discord_user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        user = User(discord_user_id=discord_user_id, username=f"User_{discord_user_id[:6]}")
        db.add(user)

    user.active_project_id = project_id
    await db.commit()
    return {
        "status": "success",
        "user_id": user.id,
        "active_project_id": project_id,
    }


@router.get("/{project_id}/truth")
async def get_shared_truth(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    mem = ProjectMemory(db)
    truth = await mem.get_shared_truth(project_id)
    return truth


@router.post("/{project_id}/decisions")
async def record_decision(
    project_id: int,
    req: DecisionRequest,
    db: AsyncSession = Depends(get_db),
):
    mem = ProjectMemory(db)
    rec = await mem.record_decision(
        project_id=project_id,
        title=req.title,
        context=req.context,
        decision=req.decision,
        rationale=req.rationale,
        user_id=req.user_id,
    )
    return {"id": rec.id, "title": rec.title, "status": rec.status}


@router.post("/{project_id}/tasks")
async def add_task(
    project_id: int,
    req: TaskRequest,
    db: AsyncSession = Depends(get_db),
):
    mem = ProjectMemory(db)
    task = await mem.add_task(project_id, req.title, req.user_id)
    return {"id": task.id, "title": task.title, "status": task.status}


@router.get("/{project_id}/tasks")
async def list_tasks(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    mem = ProjectMemory(db)
    tasks = await mem.list_tasks(project_id)
    return [{"id": t.id, "title": t.title, "status": t.status} for t in tasks]


@router.post("/user/{discord_user_id}/scratchpad")
async def append_scratchpad(
    discord_user_id: str,
    username: str,
    req: ScratchpadRequest,
    db: AsyncSession = Depends(get_db),
):
    user_mgr = UserScratchpadManager(db)
    user = await user_mgr.get_or_create_user(discord_user_id, username)
    content = await user_mgr.append_to_scratchpad(user.id, req.note, req.project_id)
    return {"user": user.username, "content": content}
