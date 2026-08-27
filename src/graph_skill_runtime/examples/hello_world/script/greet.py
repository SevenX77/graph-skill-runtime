"""Hello world example tool for graph_skill_runtime."""

from __future__ import annotations

from typing import Any


def greet(ctx: dict[str, Any]) -> str:
    """Generate a greeting message.

    Args:
        ctx: Context dictionary containing workflow state.
            Expected key: "user_name" (optional, defaults to "World")

    Returns:
        A personalized greeting message.
    """
    name = ctx.get("user_name", "World")
    greeting = f"Hello, {name}! Welcome to graph_skill_runtime."
    ctx["greeting"] = greeting
    ctx["message"] = "Greeting generated successfully"
    return greeting


def greet_with_name(ctx: dict[str, Any], name: str) -> str:
    """Generate a greeting with explicit name parameter.

    This variant accepts name as a parameter for direct invocation.

    Args:
        ctx: Context dictionary
        name: The name to greet

    Returns:
        A personalized greeting message.
    """
    greeting = f"Hello, {name}! Welcome to graph_skill_runtime."
    ctx["greeting"] = greeting
    return greeting
