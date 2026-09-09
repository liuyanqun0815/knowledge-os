from dataclasses import dataclass
from typing import Any, Protocol

from memory.models import Procedure


@dataclass
class RecallContext:
    episodes: list[dict[str, Any]]
    semantics: list[dict[str, Any]]


class MemoryPort(Protocol):
    def remember_episode(self, session_id: str, episode: dict) -> None: ...

    def recall(self, query: str, session_id: str | None) -> RecallContext: ...

    def remember_procedure(self, procedure: Procedure) -> None: ...

    def get_procedure(self, name: str) -> Procedure | None: ...
