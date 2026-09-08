from __future__ import annotations

from typing import Protocol

from knowledge_base.models import KnowledgeBase


class KnowledgeBasePort(Protocol):
    def create(self, name: str, domain_type: str, description: str = "") -> KnowledgeBase: ...

    def get(self, id: str) -> KnowledgeBase | None: ...

    def list(self, include_archived: bool = False) -> list[KnowledgeBase]: ...

    def update(
        self,
        id: str,
        *,
        name: str | None = None,
        domain_type: str | None = None,
        description: str | None = None,
    ) -> KnowledgeBase | None: ...

    def archive(self, id: str) -> KnowledgeBase | None: ...
