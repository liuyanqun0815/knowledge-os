"""Backward-compatible shim — prefer ``akos.adapters.llm.client``."""

from akos.adapters.llm.client import LlmConfigError, OpenAiCompatibleClient

__all__ = ["LlmConfigError", "OpenAiCompatibleClient"]
