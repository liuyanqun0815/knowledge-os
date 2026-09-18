from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from infra.db import get_engine
from akos.domain.models.knowledge_base import KnowledgeBase


def _row_to_kb(row: Any) -> KnowledgeBase:
    return KnowledgeBase(
        id=row.id,
        name=row.name,
        domain_type=row.domain_type,
        description=row.description or "",
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PgKnowledgeBaseRepo:
    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine or get_engine()

    def create(self, name: str, domain_type: str, description: str = "") -> KnowledgeBase:
        kb_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO knowledge_bases (
                        id, name, domain_type, description, status, created_at, updated_at
                    ) VALUES (
                        :id, :name, :domain_type, :description, 'active', :created_at, :updated_at
                    )
                    """),
                {
                    "id": kb_id,
                    "name": name,
                    "domain_type": domain_type,
                    "description": description,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        return KnowledgeBase(
            id=kb_id,
            name=name,
            domain_type=domain_type,
            description=description,
            status="active",
            created_at=now,
            updated_at=now,
        )

    def get(self, id: str) -> KnowledgeBase | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, name, domain_type, description, status, created_at, updated_at
                    FROM knowledge_bases
                    WHERE id = :id
                    """),
                {"id": id},
            ).one_or_none()
        if row is None:
            return None
        return _row_to_kb(row)

    def list(self, include_archived: bool = False) -> list[KnowledgeBase]:
        sql = """
            SELECT id, name, domain_type, description, status, created_at, updated_at
            FROM knowledge_bases
        """
        if not include_archived:
            sql += " WHERE status != 'archived'"
        sql += " ORDER BY created_at"
        with self._engine.connect() as conn:
            rows = conn.execute(text(sql)).fetchall()
        return [_row_to_kb(row) for row in rows]

    def update(
        self,
        id: str,
        *,
        name: str | None = None,
        domain_type: str | None = None,
        description: str | None = None,
    ) -> KnowledgeBase | None:
        existing = self.get(id)
        if existing is None:
            return None
        new_name = name if name is not None else existing.name
        new_domain_type = domain_type if domain_type is not None else existing.domain_type
        new_description = description if description is not None else existing.description
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE knowledge_bases
                    SET name = :name,
                        domain_type = :domain_type,
                        description = :description,
                        updated_at = :updated_at
                    WHERE id = :id
                    """),
                {
                    "id": id,
                    "name": new_name,
                    "domain_type": new_domain_type,
                    "description": new_description,
                    "updated_at": now,
                },
            )
        return KnowledgeBase(
            id=id,
            name=new_name,
            domain_type=new_domain_type,
            description=new_description,
            status=existing.status,
            created_at=existing.created_at,
            updated_at=now,
        )

    def archive(self, id: str) -> KnowledgeBase | None:
        existing = self.get(id)
        if existing is None:
            return None
        now = datetime.now(timezone.utc)
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    UPDATE knowledge_bases
                    SET status = 'archived', updated_at = :updated_at
                    WHERE id = :id
                    """),
                {"id": id, "updated_at": now},
            )
        return KnowledgeBase(
            id=existing.id,
            name=existing.name,
            domain_type=existing.domain_type,
            description=existing.description,
            status="archived",
            created_at=existing.created_at,
            updated_at=now,
        )
