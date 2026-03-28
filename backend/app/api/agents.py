from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.agent import Agent
from app.models.agent_user import AgentUser
from app.models.user import User
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse, AgentUserResponse, AgentUserUpdate
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentResponse])
async def list_agents(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Agent).order_by(Agent.id.desc()))
    return result.scalars().all()


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(body: AgentCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    agent = Agent(
        name=body.name,
        agent_type=body.agent_type,
        bot_token=body.bot_token,
        config=body.config,
        created_by=user.id,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int, body: AgentUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()


@router.post("/{agent_id}/activate", response_model=AgentResponse)
async def activate_agent(agent_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_active = True
    await db.commit()
    await db.refresh(agent)
    return agent


@router.post("/{agent_id}/deactivate", response_model=AgentResponse)
async def deactivate_agent(agent_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_active = False
    await db.commit()
    await db.refresh(agent)
    return agent


# Agent Users
@router.get("/{agent_id}/users", response_model=list[AgentUserResponse])
async def list_agent_users(
    agent_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)
):
    result = await db.execute(select(AgentUser).where(AgentUser.agent_id == agent_id).order_by(AgentUser.id))
    return result.scalars().all()


@router.put("/{agent_id}/users/{user_id}", response_model=AgentUserResponse)
async def update_agent_user(
    agent_id: int,
    user_id: int,
    body: AgentUserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentUser).where(AgentUser.agent_id == agent_id, AgentUser.id == user_id)
    )
    agent_user = result.scalar_one_or_none()
    if not agent_user:
        raise HTTPException(status_code=404, detail="Agent user not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(agent_user, field, value)
    await db.commit()
    await db.refresh(agent_user)
    return agent_user
