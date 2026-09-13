from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.memory.project_memory import ProjectMemory
from src.memory.user_scratchpad import UserScratchpadManager
from src.storage.database import get_db

router = APIRouter(prefix="/projects", tags=["projects"])


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


@router.post("/create")
async def create_project(
    name: str,
    description: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    mem = ProjectMemory(db)
    proj = await mem.get_or_create_project(name, description)
    return {"id": proj.id, "name": proj.name, "description": proj.description}


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
