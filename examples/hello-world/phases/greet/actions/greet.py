"""Deterministic action used by the repository's portable hello-world gSkill."""

from __future__ import annotations

from typing import Any


def greet(inputs: dict[str, Any]) -> dict[str, str]:
    """Return a greeting without mutating the input blackboard slice."""

    name = inputs.get("name", "World")
    return {"greeting": f"Hello, {name}! Welcome to Graph Skill Runtime."}
