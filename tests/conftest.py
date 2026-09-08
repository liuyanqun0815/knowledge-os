import pytest


@pytest.fixture
def any_uuid() -> str:
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def build_orchestrator_deps():
    from infra.bootstrap import build_orchestrator_deps as _build

    return _build
