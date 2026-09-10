from __future__ import annotations

from dataclasses import replace

from compiler.extraction_spec import LlmExtractionSpec
from infra.settings import Settings


def apply_open_flag(spec: LlmExtractionSpec, settings: Settings) -> LlmExtractionSpec:
    return replace(spec, open_predicates=settings.extract_open_predicates)
