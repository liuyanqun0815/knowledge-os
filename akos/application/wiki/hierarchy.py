"""Pure hierarchy assignment: map raw topic names to hub / leaf / snippet."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

_HUB_KEYWORDS = ("流程", "规范", "指南", "升级")
_RANK_MARKERS = ("一级", "二级", "三级")
_DEFAULT_HUB = "未分类"


@dataclass(frozen=True)
class HierarchyAssignment:
    raw_name: str
    hub: str
    leaf: str | None  # None => hub-only (_index)
    role: str  # "hub" | "leaf" | "snippet"
    target_leaf: str | None  # for snippet: which leaf (or None => hub _index)


@dataclass
class HierarchyPlan:
    assignments: dict[str, HierarchyAssignment]  # key = display/raw topic name
    hubs: dict[str, list[str]]  # hub -> leaf display names (excl snippets)


def _seed_lookup(
    name: str,
    parents: dict[str, tuple[str, str | None, str]],
    snippets: dict[str, tuple[str, str | None, str]],
) -> HierarchyAssignment | None:
    if name in snippets:
        hub, target, _role = snippets[name]
        return HierarchyAssignment(name, hub, None, "snippet", target)
    if name in parents:
        hub, leaf, role = parents[name]
        if role == "hub" or leaf is None:
            return HierarchyAssignment(name, hub, None, "hub", None)
        return HierarchyAssignment(name, hub, leaf, "leaf", None)
    return None


def _has_hub_keyword(name: str) -> bool:
    return any(k in name for k in _HUB_KEYWORDS)


def _is_short_snippet_candidate(name: str) -> bool:
    return len(name) <= 4 and not _has_hub_keyword(name)


def _is_escalation_rank(name: str) -> bool:
    return any(m in name for m in _RANK_MARKERS)


def _match_hub_by_prefix(name: str, known_hubs: set[str]) -> str | None:
    """Prefer longest hub whose prefix (首字/二字) matches name start, e.g. 客服* → 客服话术."""
    best: str | None = None
    for hub in known_hubs:
        if hub == _DEFAULT_HUB:
            continue
        # Full hub prefix
        if name.startswith(hub) and name != hub:
            if best is None or len(hub) > len(best):
                best = hub
            continue
        # Shared leading characters (at least 2) — 客服开场 → 客服话术
        prefix_len = 0
        for a, b in zip(name, hub):
            if a != b:
                break
            prefix_len += 1
        if prefix_len >= 2 and name != hub:
            if best is None or len(hub) > len(best):
                best = hub
    return best


def _heuristic_assign(
    name: str,
    hub_counts: Counter[str],
    known_hubs: set[str],
) -> HierarchyAssignment:
    if _is_escalation_rank(name):
        return HierarchyAssignment(name, "投诉升级", name, "leaf", None)

    if _is_short_snippet_candidate(name):
        hub = hub_counts.most_common(1)[0][0] if hub_counts else _DEFAULT_HUB
        return HierarchyAssignment(name, hub, None, "snippet", None)

    matched = _match_hub_by_prefix(name, known_hubs)
    if matched:
        leaf = name[len(matched) :] if name.startswith(matched) else name
        leaf = leaf or name
        return HierarchyAssignment(name, matched, leaf, "leaf", None)

    return HierarchyAssignment(name, name, None, "hub", None)


def _build_hubs(assignments: dict[str, HierarchyAssignment]) -> dict[str, list[str]]:
    hubs: dict[str, list[str]] = defaultdict(list)
    seen: dict[str, set[str]] = defaultdict(set)

    for a in assignments.values():
        hubs.setdefault(a.hub, [])
        leaf_name: str | None = None
        if a.role == "leaf" and a.leaf:
            leaf_name = a.leaf
        elif a.role == "snippet" and a.target_leaf:
            leaf_name = a.target_leaf
        if leaf_name and leaf_name not in seen[a.hub]:
            seen[a.hub].add(leaf_name)
            hubs[a.hub].append(leaf_name)

    return dict(hubs)


def assign_wiki_hierarchy(
    names: list[str],
    *,
    seeds: dict | None = None,
) -> HierarchyPlan:
    """Map raw topic names to hub/leaf/snippet using seeds + heuristics."""
    parents: dict[str, tuple[str, str | None, str]] = {}
    snippets: dict[str, tuple[str, str | None, str]] = {}
    if seeds:
        parents = dict(seeds.get("parents") or {})
        snippets = dict(seeds.get("snippets") or {})

    assignments: dict[str, HierarchyAssignment] = {}
    deferred: list[str] = []

    for name in names:
        seeded = _seed_lookup(name, parents, snippets)
        if seeded is not None:
            assignments[name] = seeded
        else:
            deferred.append(name)

    hub_counts: Counter[str] = Counter(a.hub for a in assignments.values())
    known_hubs: set[str] = set(hub_counts)
    known_hubs.update(hub for hub, _leaf, _role in parents.values())
    known_hubs.update(hub for hub, _leaf, _role in snippets.values())

    for name in deferred:
        a = _heuristic_assign(name, hub_counts, known_hubs)
        assignments[name] = a
        if a.role != "snippet":
            hub_counts[a.hub] += 1
            known_hubs.add(a.hub)

    return HierarchyPlan(assignments=assignments, hubs=_build_hubs(assignments))
