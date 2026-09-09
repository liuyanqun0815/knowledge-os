from evolution.ports import ApplyReport, EvolutionPort, KnowledgeDiff


def diff_sources(evolution: EvolutionPort, old_source_id: str, new_source_id: str) -> KnowledgeDiff:
    return evolution.diff_sources(old_source_id, new_source_id)


def apply_diff(evolution: EvolutionPort, diff: KnowledgeDiff) -> ApplyReport:
    return evolution.apply_diff(diff)
