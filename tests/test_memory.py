from memory.memory_repo import InMemoryMemoryStore


def test_episode_recall_returns_recent():
    memory_store = InMemoryMemoryStore()
    memory_store.remember_episode("sess1", {"q": "能否退货", "a": "看类目"})
    context = memory_store.recall("退货", "sess1")
    assert context.episodes
