import asyncio
from app.db.database import engine 
from app.db import models
from sqlalchemy import text 

async def init_models():
    print("Connecting to Postgresql:  ")

    async with engine.begin() as conn: ## websocket
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        await conn.run_sync(models.Base.metadata.create_all)
    print("Table created successfuly!")

asyncio.run(init_models())

