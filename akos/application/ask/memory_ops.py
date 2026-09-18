from akos.domain.ports.memory import MemoryPort, RecallContext


def recall(memory: MemoryPort, query: str, session_id: str | None) -> RecallContext:
    return memory.recall(query, session_id)


def remember(memory: MemoryPort, session_id: str, episode: dict) -> None:
    memory.remember_episode(session_id, episode)
