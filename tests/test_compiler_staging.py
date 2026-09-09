from datetime import datetime, timezone
from pathlib import Path

from compiler.rule_extractor import RuleExtractor
from compiler.service import KnowledgeCompiler
from domains.ecommerce_cs.seed import register_ecommerce_cs
from evidence.memory_repo import InMemoryEvidence
from graph.memory_repo import InMemoryGraph
from knowledge.memory_repo import InMemoryKnowledge
from knowledge.models import Event, Source
from ontology.registry import InMemoryOntology


def _compile_v4(*, staging: bool = False) -> tuple[InMemoryKnowledge, str]:
    onto = InMemoryOntology()
    register_ecommerce_cs(onto)
    knowledge = InMemoryKnowledge()
    graph = InMemoryGraph()
    evidence = InMemoryEvidence()
    src_v3 = Source(
        id="refund_policy_v3",
        title="退换货政策v3",
        type="policy",
        uri="samples/refund_policy_v3.md",
        version="3",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )
    src_v4 = Source(
        id="refund_policy_v4",
        title="退换货政策v4",
        type="policy",
        uri="samples/refund_policy_v4.md",
        version="4",
        created_at=datetime.now(timezone.utc),
        status="ready",
        replaces_source_id=src_v3.id,
    )
    knowledge.save_source(src_v3)
    knowledge.save_source(src_v4)
    knowledge.save_source_text(src_v3.id, Path("samples/refund_policy_v3.md").read_text(encoding="utf-8"))
    knowledge.save_source_text(src_v4.id, Path("samples/refund_policy_v4.md").read_text(encoding="utf-8"))
    compiler = KnowledgeCompiler(onto, knowledge, graph, evidence, RuleExtractor())
    compiler.ingest(src_v3.id)
    compiler.ingest(src_v4.id, staging=staging)
    return knowledge, src_v4.id


def test_staging_compile_writes_staging_claims_not_active():
    knowledge, v4_id = _compile_v4(staging=True)

    staging = knowledge.get_claims_by_status("staging")
    assert staging
    assert all(c.source_ids == [v4_id] for c in staging)

    freight = [c for c in staging if c.predicate == "运费承担方"]
    assert len(freight) == 1
    assert freight[0].object == "平台"
    assert freight[0].status == "staging"

    active_freight = knowledge.get_active_claims("七天无理由", "运费承担方")
    assert len(active_freight) == 1
    assert active_freight[0].object == "买家"


def test_default_compile_writes_active_claims():
    knowledge, v4_id = _compile_v4(staging=False)

    active = knowledge.get_active_claims("七天无理由")
    v4_claims = knowledge.get_claims_for_source(v4_id)
    assert v4_claims
    assert all(c.status == "active" for c in v4_claims)
    assert not knowledge.get_claims_by_status("staging")


def test_save_source_persists_replaces_source_id():
    repo = InMemoryKnowledge()
    old = Source(
        id="s-v3",
        title="v3",
        type="policy",
        uri="file://v3",
        version="3",
        created_at=datetime.now(timezone.utc),
        status="ready",
    )
    new = Source(
        id="s-v4",
        title="v4",
        type="policy",
        uri="file://v4",
        version="4",
        created_at=datetime.now(timezone.utc),
        status="ready",
        replaces_source_id="s-v3",
    )
    repo.save_source(old)
    repo.save_source(new)

    fetched = repo.get_source("s-v4")
    assert fetched is not None
    assert fetched.replaces_source_id == "s-v3"


def test_append_and_list_events():
    repo = InMemoryKnowledge()
    event = Event(
        id="evt-1",
        type="policy_changed",
        participants=["c-old", "c-new"],
        timestamp=datetime(2024, 6, 1, tzinfo=timezone.utc),
        source_id="s-v4",
    )
    repo.append_event(event)

    all_events = repo.list_events()
    assert len(all_events) == 1
    assert all_events[0].type == "policy_changed"

    filtered = repo.list_events(source_id="s-v4")
    assert len(filtered) == 1
    assert repo.list_events(source_id="missing") == []
