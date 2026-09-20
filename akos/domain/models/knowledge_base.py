from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class KnowledgeBase:
    id: str
    name: str
    domain_type: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime
    graph_enabled: bool = False
