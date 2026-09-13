from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.storage.models import User, UserScratchpad


class UserScratchpadManager:
    """Provides isolated per-researcher scratchpads and synchronization with shared project truth."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_or_create_user(self, discord_user_id: str, username: str) -> User:
        stmt = select(User).where(User.discord_user_id == discord_user_id)
        res = await self.db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            user = User(discord_user_id=discord_user_id, username=username)
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)
        return user

    async def append_to_scratchpad(self, user_id: int, note_text: str, project_id: Optional[int] = None) -> str:
        stmt = select(UserScratchpad).where(UserScratchpad.user_id == user_id, UserScratchpad.project_id == project_id)
        res = await self.db.execute(stmt)
        pad = res.scalar_one_or_none()

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        entry = f"[{timestamp}] {note_text}\n"

        if not pad:
            pad = UserScratchpad(user_id=user_id, project_id=project_id, content=entry)
            self.db.add(pad)
        else:
            pad.content = (pad.content or "") + entry

        await self.db.commit()
        await self.db.refresh(pad)
        return pad.content

    async def get_scratchpad(self, user_id: int, project_id: Optional[int] = None) -> str:
        stmt = select(UserScratchpad).where(UserScratchpad.user_id == user_id, UserScratchpad.project_id == project_id)
        res = await self.db.execute(stmt)
        pad = res.scalar_one_or_none()
        return pad.content if pad else "Scratchpad is empty."

    async def clear_scratchpad(self, user_id: int, project_id: Optional[int] = None) -> None:
        stmt = select(UserScratchpad).where(UserScratchpad.user_id == user_id, UserScratchpad.project_id == project_id)
        res = await self.db.execute(stmt)
        pad = res.scalar_one_or_none()
        if pad:
            pad.content = ""
            await self.db.commit()
