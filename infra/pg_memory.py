from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from memory.ports import RecallContext


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
