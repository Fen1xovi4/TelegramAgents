import importlib
import pkgutil

from app.agents.base import BaseAgent


class AgentRegistry:
    _agents: dict[str, type[BaseAgent]] = {}

    @classmethod
    def register(cls, agent_class: type[BaseAgent]):
        cls._agents[agent_class.agent_type] = agent_class
        return agent_class

    @classmethod
    def get(cls, agent_type: str) -> BaseAgent:
        if agent_type not in cls._agents:
            raise ValueError(f"Unknown agent type: {agent_type}")
        return cls._agents[agent_type]()

    @classmethod
    def all_types(cls) -> list[str]:
        return list(cls._agents.keys())

    @classmethod
    def discover(cls):
        package = importlib.import_module("app.agents")
        for _, name, is_pkg in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
            if is_pkg:
                try:
                    importlib.import_module(f"{name}.agent")
                except ModuleNotFoundError:
                    pass
