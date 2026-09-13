from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.models import Project, ProjectDecision, ProjectTask


class ProjectMemory:
    """Manages project-level shared truth, hypotheses, decision history, and tasks."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_project(
        self,
        name: str,
        research_goal: Optional[str] = None,
        description: Optional[str] = None,
    ) -> Project:
        stmt = select(Project).where(Project.name == name)
        res = await self.db.execute(stmt)
        project = res.scalar_one_or_none()
        if not project:
            goal = research_goal or description
            project = Project(name=name, research_goal=goal)
            self.db.add(project)
            await self.db.commit()
            await self.db.refresh(project)
        return project

    async def record_decision(
        self,
        project_id: int,
        title: str,
        context: str,
        decision: str,
        rationale: str,
        user_id: Optional[int] = None,
    ) -> ProjectDecision:
        record = ProjectDecision(
            project_id=project_id,
            user_id=user_id,
            title=title,
            context=context,
            decision=decision,
            rationale=rationale,
            status="accepted",
        )
        self.db.add(record)
        await self.db.commit()
        await self.db.refresh(record)
        return record

    async def get_decisions(self, project_id: int) -> List[ProjectDecision]:
        stmt = select(ProjectDecision).where(ProjectDecision.project_id == project_id).order_by(ProjectDecision.created_at.desc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def add_task(
        self,
        project_id: int,
        title: str,
        user_id: Optional[int] = None,
    ) -> ProjectTask:
        task = ProjectTask(project_id=project_id, title=title, assigned_user_id=user_id, status="todo")
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def list_tasks(self, project_id: int) -> List[ProjectTask]:
        stmt = select(ProjectTask).where(ProjectTask.project_id == project_id).order_by(ProjectTask.id.asc())
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_shared_truth(self, project_id: int) -> Dict[str, Any]:
        stmt = select(Project).where(Project.id == project_id)
        res = await self.db.execute(stmt)
        proj = res.scalar_one_or_none()
        decisions = await self.get_decisions(project_id)
        tasks = await self.list_tasks(project_id)

        return {
            "project_name": proj.name if proj else "Default",
            "research_goal": proj.research_goal if proj else "",
            "research_question": proj.research_goal if proj else "",
            "inclusion_criteria": proj.inclusion_criteria if proj else {},
            "exclusion_criteria": proj.exclusion_criteria if proj else {},
            "decisions": [
                {"title": d.title, "decision": d.decision, "rationale": d.rationale}
                for d in decisions
            ],
            "active_tasks": [
                {"id": t.id, "title": t.title, "status": t.status}
                for t in tasks if t.status != "done"
            ],
        }
