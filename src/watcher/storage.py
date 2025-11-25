# src/watcher/storage.py
from typing import Optional, List, Dict
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

# No longer importing AsyncSessionLocal, User, LastTx globally here
# These will be passed via session_factory or imported within methods if needed
from src.models import (
    LastTx,
)  # Import only models needed for type hinting/ORM operations

DB_FILE = "tx_storage.db"


class TxStorage:
    def __init__(self, user_id: int):
        self.user_id = user_id

    async def load_last(self, session: AsyncSession) -> Optional[str]:
        result = await session.execute(
            select(LastTx.last_timestamp).where(LastTx.user_id == self.user_id)
        )
        return result.scalar_one_or_none()

    async def save_last(self, session: AsyncSession, timestamp: str):
        last_tx = await session.get(LastTx, self.user_id)
        if last_tx:
            last_tx.last_timestamp = timestamp
        else:
            last_tx = LastTx(user_id=self.user_id, last_timestamp=timestamp)
            session.add(last_tx)

    async def filter_new(
        self, session: AsyncSession, deposits: List[Dict]
    ) -> List[Dict]:
        last = await self.load_last(session)
        if not last:
            return deposits
        return [d for d in deposits if d["block_timestamp"] > last]

    async def reset(self, session: AsyncSession):
        """Reset: borra tu registro de last_tx"""
        await session.execute(delete(LastTx).where(LastTx.user_id == self.user_id))
        print(f"RESET COMPLETADO → user_id {self.user_id}")
