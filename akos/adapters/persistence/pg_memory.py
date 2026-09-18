from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from memory.models import Procedure, Step
from akos.domain.ports.memory import RecallContext


class PgMemory:
    """PostgreSQL memory store scoped to a single knowledge base."""

    def __init__(self, engine: Engine, knowledge_base_id: str, max_episodes: int = 10) -> None:
        self._engine = engine
        self._knowledge_base_id = knowledge_base_id
        self._max_episodes = max_episodes

    def remember_episode(self, session_id: str, episode: dict) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO memory_episodes (knowledge_base_id, session_id, episode)
                    VALUES (:knowledge_base_id, :session_id, CAST(:episode AS jsonb))
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "session_id": session_id,
                    "episode": json.dumps(episode),
                },
            )
            conn.execute(
                text("""
                    DELETE FROM memory_episodes
                    WHERE id IN (
                        SELECT id
                        FROM memory_episodes
                        WHERE knowledge_base_id = :knowledge_base_id
                          AND session_id = :session_id
                        ORDER BY created_at DESC
                        OFFSET :max_episodes
                    )
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "session_id": session_id,
                    "max_episodes": self._max_episodes,
                },
            )

    def recall(self, query: str, session_id: str | None) -> RecallContext:
        episodes: list[dict] = []
        if session_id:
            with self._engine.connect() as conn:
                rows = conn.execute(
                    text("""
                        SELECT episode
                        FROM memory_episodes
                        WHERE knowledge_base_id = :knowledge_base_id
                          AND session_id = :session_id
                        ORDER BY created_at DESC
                        """),
                    {
                        "knowledge_base_id": self._knowledge_base_id,
                        "session_id": session_id,
                    },
                ).fetchall()

            session_episodes: list[dict] = []
            for row in rows:
                episode = row.episode
                if isinstance(episode, str):
                    episode = json.loads(episode)
                session_episodes.append(dict(episode))

            for episode in session_episodes:
                episode_text = str(episode)
                if any(token in episode_text for token in query.split() if token):
                    episodes.append(episode)
            if not episodes and session_episodes:
                episodes = session_episodes[:3]

        semantics = self._recall_semantics(query)
        return RecallContext(episodes=episodes, semantics=semantics)

    def _recall_semantics(self, query: str) -> list[dict[str, Any]]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                text("""
                    SELECT key, value
                    FROM memory_semantics
                    WHERE knowledge_base_id = :knowledge_base_id
                    """),
                {"knowledge_base_id": self._knowledge_base_id},
            ).fetchall()

        semantics: list[dict[str, Any]] = []
        for row in rows:
            if row.key in query or query in row.key:
                value = row.value
                if isinstance(value, str):
                    value = json.loads(value)
                semantics.append({"key": row.key, **dict(value)})
        return semantics

    def remember_procedure(self, procedure: Procedure) -> None:
        steps_payload = [
            {
                "order": step.order,
                "description": step.description,
                "claim_refs": step.claim_refs,
            }
            for step in procedure.steps
        ]
        with self._engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO procedures (
                        id, knowledge_base_id, name, steps, ontology_refs, domain
                    )
                    VALUES (
                        :id, :knowledge_base_id, :name,
                        CAST(:steps AS jsonb), CAST(:ontology_refs AS jsonb), :domain
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        name = EXCLUDED.name,
                        steps = EXCLUDED.steps,
                        ontology_refs = EXCLUDED.ontology_refs,
                        domain = EXCLUDED.domain
                    """),
                {
                    "id": procedure.id,
                    "knowledge_base_id": self._knowledge_base_id,
                    "name": procedure.name,
                    "steps": json.dumps(steps_payload),
                    "ontology_refs": json.dumps(procedure.ontology_refs),
                    "domain": procedure.domain,
                },
            )

    def get_procedure(self, name: str) -> Procedure | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                text("""
                    SELECT id, name, steps, ontology_refs, domain
                    FROM procedures
                    WHERE knowledge_base_id = :knowledge_base_id
                      AND (
                        name = :name
                        OR :name ILIKE '%' || name || '%'
                        OR name ILIKE '%' || :name || '%'
                      )
                    ORDER BY length(name) DESC
                    LIMIT 1
                    """),
                {
                    "knowledge_base_id": self._knowledge_base_id,
                    "name": name,
                },
            ).fetchone()
        if row is None:
            return None
        return self._row_to_procedure(row)

    @staticmethod
    def _row_to_procedure(row: Any) -> Procedure:
        steps_data = row.steps
        if isinstance(steps_data, str):
            steps_data = json.loads(steps_data)
        ontology_refs = row.ontology_refs
        if isinstance(ontology_refs, str):
            ontology_refs = json.loads(ontology_refs)
        steps = [
            Step(
                order=int(item["order"]),
                description=str(item["description"]),
                claim_refs=list(item.get("claim_refs") or []),
            )
            for item in steps_data
        ]
        return Procedure(
            id=row.id,
            name=row.name,
            steps=steps,
            ontology_refs=list(ontology_refs),
            domain=row.domain,
        )
