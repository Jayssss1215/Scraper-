from abc import ABC, abstractmethod
from typing import List

from src.models import Lead, MissionRequest


class ProviderError(RuntimeError):
    pass


class LeadProvider(ABC):
    @abstractmethod
    def search(self, mission: MissionRequest) -> List[Lead]:
        raise NotImplementedError

