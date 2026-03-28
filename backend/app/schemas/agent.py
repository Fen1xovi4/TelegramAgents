from datetime import datetime

from pydantic import BaseModel


class AgentCreate(BaseModel):
    name: str
    agent_type: str
    bot_token: str
    config: dict = {}


class AgentUpdate(BaseModel):
    name: str | None = None
    bot_token: str | None = None
    config: dict | None = None


class AgentResponse(BaseModel):
    id: int
    name: str
    agent_type: str
    bot_token: str
    bot_username: str | None
    config: dict
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AgentUserResponse(BaseModel):
    id: int
    agent_id: int
    telegram_id: int
    telegram_username: str | None
    display_name: str | None
    role: str
    is_blocked: bool

    model_config = {"from_attributes": True}


class AgentUserUpdate(BaseModel):
    role: str | None = None
    is_blocked: bool | None = None
