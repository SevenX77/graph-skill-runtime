"""Explicit startup settings for graph_skill_runtime."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Settings object loaded once at startup instead of mutating env vars."""

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    graph_skill_runtime_api_key: str | None = None
    graph_skill_runtime_model_provider: str | None = None
    graph_skill_runtime_model: str | None = None
    openai_model: str | None = None
    graph_skill_runtime_default_role: str = "balanced"
    graph_skill_runtime_persona_path: str | None = None
    studio_checkpointer: str | None = None
    graph_skill_runtime_checkpointer_db: str | None = None
    log_level: str = "INFO"
    debug_mode: bool = False

    @classmethod
    def from_env(cls, env_overrides: dict[str, str] | None = None) -> Settings:
        """Build Settings from process env plus explicit override values."""

        env = _EnvView(os.environ, env_overrides or {})
        return cls(
            openai_api_key=env.optional("OPENAI_API_KEY"),
            anthropic_api_key=env.optional("ANTHROPIC_API_KEY"),
            graph_skill_runtime_api_key=env.optional("GRAPH_SKILL_RUNTIME_API_KEY"),
            graph_skill_runtime_model_provider=env.optional("GRAPH_SKILL_RUNTIME_MODEL_PROVIDER"),
            graph_skill_runtime_model=env.optional("GRAPH_SKILL_RUNTIME_MODEL"),
            openai_model=env.optional("OPENAI_MODEL"),
            graph_skill_runtime_default_role=env.get("GRAPH_SKILL_RUNTIME_DEFAULT_ROLE", "balanced"),
            graph_skill_runtime_persona_path=env.optional("GRAPH_SKILL_RUNTIME_PERSONA_PATH"),
            studio_checkpointer=env.optional("STUDIO_CHECKPOINTER"),
            graph_skill_runtime_checkpointer_db=env.optional("GRAPH_SKILL_RUNTIME_CHECKPOINTER_DB"),
            log_level=env.get("GRAPH_SKILL_RUNTIME_LOG_LEVEL", "INFO").upper(),
            debug_mode=env.bool("GRAPH_SKILL_RUNTIME_DEBUG", default=False),
        )


class _EnvView:
    """Read-only overlay of environment variables for Settings loading."""

    def __init__(self, base: Mapping[str, str], overrides: Mapping[str, str]) -> None:
        self._base = base
        self._overrides = overrides

    def optional(self, key: str) -> str | None:
        value = self.get(key, "")
        return value or None

    def get(self, key: str, default: str) -> str:
        value = self._overrides.get(key)
        if value is None:
            value = self._base.get(key)
        if value is None or value == "":
            return default
        return value

    def bool(self, key: str, *, default: bool) -> bool:
        value = self.optional(key)
        if value is None:
            return default
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "on"}:
            return True
        if normalized in {"0", "false", "no", "n", "off"}:
            return False
        raise ValueError(
            f"Invalid boolean value for {key}: {value!r}. "
            "Expected one of true/false/1/0/yes/no/on/off."
        )


__all__ = ["Settings"]
