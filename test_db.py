import asyncio
import os
import sys
from backend.database import AsyncSessionLocal
from sqlalchemy import text

async def test():
    db = AsyncSessionLocal()
    res = await db.execute(text('SELECT * FROM chat_history LIMIT 1;'))
    print(res.fetchall())
    await db.close()

if __name__ == '__main__':
    asyncio.run(test())
