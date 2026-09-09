from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LlmExtractionSpec:
    allowed_predicates: list[str]
    entity_types: list[str]
    prompt_locale: str = "zh"
    few_shot_hints: list[str] | None = None
