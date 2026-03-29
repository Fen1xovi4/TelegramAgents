from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class AgentMessage:
    telegram_id: int
    chat_id: int
    text: str
    role: str
    agent_id: int
    agent_config: dict = field(default_factory=dict)


@dataclass
class AgentResponse:
    text: str
    intent: str | None = None
    intent_data: dict | None = None
    buttons: list[str] | None = None


class BaseAgent(ABC):
    agent_type: str

    @abstractmethod
    async def handle_message(self, message: AgentMessage, db: AsyncSession) -> AgentResponse: ...

    @abstractmethod
    def get_default_config(self) -> dict: ...

    @abstractmethod
    def get_roles(self) -> list[str]: ...
