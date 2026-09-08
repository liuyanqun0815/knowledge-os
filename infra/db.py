from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from infra.settings import Settings

_engine: Engine | None = None


def get_engine(settings: Settings | None = None) -> Engine:
    global _engine
    if _engine is None:
        cfg = settings or Settings()
        _engine = create_engine(cfg.database_url, pool_pre_ping=True)
    return _engine


def reset_engine() -> None:
    """Reset cached engine (useful in tests)."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
