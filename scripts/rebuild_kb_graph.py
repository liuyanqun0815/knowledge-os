"""Rebuild topic graph and purge orphan chunk/topic rows for a knowledge base."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild topic clusters and purge stale graph rows")
    parser.add_argument("kb_id", help="Knowledge base id")
    args = parser.parse_args()

    from akos.bootstrap import build_orchestrator_for_kb
    from akos.adapters.persistence.pg_graph import PgGraph
    from infra.settings import Settings
    from knowledge.topic_service import rebuild_topic_clusters

    settings = Settings()
    orchestrator = build_orchestrator_for_kb(args.kb_id)
    deps = orchestrator.deps
    if settings.topic_cluster:
        rebuild_topic_clusters(deps.knowledge, deps.graph, deps.knowledge_base_id, settings)
    if isinstance(deps.graph, PgGraph):
        deps.graph.purge_orphans()
    print(f"Rebuilt topic graph for knowledge base {args.kb_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
