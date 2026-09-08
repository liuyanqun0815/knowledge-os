from memory.ports import RecallContext


class InMemoryMemoryStore:
    def __init__(self, max_episodes: int = 10) -> None:
        self._episodes: dict[str, list[dict]] = {}
        self._semantics: dict[str, dict] = {}
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
