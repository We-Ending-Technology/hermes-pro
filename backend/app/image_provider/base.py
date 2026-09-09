from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class ImageResult:
    url: str
    provider: str


class ImageProvider(ABC):
    provider: str

    @abstractmethod
    async def generate_cover(self, prompt: str) -> ImageResult:
        raise NotImplementedError
