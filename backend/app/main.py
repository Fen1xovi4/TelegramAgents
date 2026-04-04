import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.agents.registry import AgentRegistry
from app.database import async_session, engine
from app.models import Base, User, Agent
from app.api import auth, agents, logs, bookstore, settings, video_shorts
from app.api.auth import hash_password
from app.services.telegram_bot_manager import bot_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_default_admin():
    async with async_session() as db:
        result = await db.execute(select(User).where(User.email == "admin@admin.com"))
        if not result.scalar_one_or_none():
            user = User(
                email="admin@admin.com",
                password_hash=hash_password("admin"),
                display_name="Admin",
                is_superadmin=True,
            )
            db.add(user)
            await db.commit()
            logger.info("Default admin created: admin@admin.com / admin")


async def start_active_bots():
    async with async_session() as db:
        result = await db.execute(select(Agent).where(Agent.is_active == True))
        for agent in result.scalars().all():
            try:
                await bot_manager.start_bot(agent.id, agent.bot_token, agent.agent_type)
            except Exception as e:
                logger.error(f"Failed to start bot for agent {agent.id}: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AgentRegistry.discover()
    logger.info(f"Registered agent types: {AgentRegistry.all_types()}")

    await create_default_admin()
    await start_active_bots()

    yield

    # Shutdown
    await bot_manager.stop_all()
    await engine.dispose()


app = FastAPI(title="Telegram Agents Platform", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3333"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(agents.router)
app.include_router(logs.router)
app.include_router(bookstore.router)
app.include_router(settings.router)
app.include_router(video_shorts.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "agent_types": AgentRegistry.all_types()}
