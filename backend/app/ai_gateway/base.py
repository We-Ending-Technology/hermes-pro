from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class AIResponse:
    content: str
    provider: str
    model: str

class AIGateway(ABC):
    @abstractmethod
    async def complete(self, prompt: str, *, system: str | None = None) -> AIResponse:
        raise NotImplementedError
