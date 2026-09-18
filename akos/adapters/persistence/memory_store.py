from memory.models import Procedure
from memory.ports import RecallContext


class InMemoryMemoryStore:
    def __init__(self, max_episodes: int = 10) -> None:
        self._episodes: dict[str, list[dict]] = {}
        self._semantics: dict[str, dict] = {}
        self._procedures: dict[str, Procedure] = {}
        self._max_episodes = max_episodes

    def remember_episode(self, session_id: str, episode: dict) -> None:
        if session_id not in self._episodes:
            self._episodes[session_id] = []
        self._episodes[session_id].append(episode)
        if len(self._episodes[session_id]) > self._max_episodes:
            self._episodes[session_id] = self._episodes[session_id][-self._max_episodes :]

    def recall(self, query: str, session_id: str | None) -> RecallContext:
        episodes: list[dict] = []
        if session_id and session_id in self._episodes:
            for episode in reversed(self._episodes[session_id]):
                episode_text = str(episode)
                if any(token in episode_text for token in query.split() if token):
                    episodes.append(episode)
            if not episodes:
                episodes = self._episodes[session_id][-3:]

        semantics: list[dict] = []
        for key, value in self._semantics.items():
            if key in query or query in key:
                semantics.append({"key": key, **value})

        return RecallContext(episodes=episodes, semantics=semantics)

    def remember_procedure(self, procedure: Procedure) -> None:
        self._procedures[procedure.name] = procedure

    def get_procedure(self, name: str) -> Procedure | None:
        if name in self._procedures:
            return self._procedures[name]
        for procedure_name, procedure in self._procedures.items():
            if procedure_name in name or name in procedure_name:
                return procedure
        return None
