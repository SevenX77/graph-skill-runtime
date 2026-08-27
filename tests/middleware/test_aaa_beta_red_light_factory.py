"""RED-LIGHT tests for PR β middleware factory.

These tests intentionally fail until β3 implements the real factory and
physical middleware skeletons.
"""

from __future__ import annotations

from graph_skill_runtime.middleware import MVP0_MIDDLEWARE_ORDER_CONTRACT


def test_beta_factory_builds_six_middlewares_in_contract_order() -> None:
    """Unit: factory must consume MVP0_MIDDLEWARE_ORDER_CONTRACT as source of truth."""

    from graph_skill_runtime.middleware.factory import build_middleware_chain

    chain = build_middleware_chain(
        io_manager=object(),
        schema_engine=object(),
        current_phase_schema=object(),
        phase_name="main",
        unattended=False,
        interrupt_fn=None,
    )

    def contract_name(middleware: object) -> str:
        name = type(middleware).__name__.removesuffix("Middleware")
        if name == "ToolErrorHandling":
            return "ToolError"
        return name

    names = tuple(contract_name(middleware) for middleware in chain)

    assert names == MVP0_MIDDLEWARE_ORDER_CONTRACT


def test_beta_factory_does_not_copy_a_parallel_order_list() -> None:
    """Unit: PR β must not maintain a second hard-coded middleware order."""

    import graph_skill_runtime.middleware.factory as factory

    assert factory.MIDDLEWARE_ORDER_CONTRACT is MVP0_MIDDLEWARE_ORDER_CONTRACT


def test_beta_tracing_tool_error_loop_detection_skeletons_are_physical_classes() -> None:
    """Unit: missing middleware layers must exist as importable AgentMiddleware skeletons."""

    from langchain.agents.middleware import AgentMiddleware

    from graph_skill_runtime.middleware.loop_detection import LoopDetectionMiddleware
    from graph_skill_runtime.middleware.tool_error import ToolErrorHandlingMiddleware
    from graph_skill_runtime.middleware.tracing import TracingMiddleware

    assert issubclass(TracingMiddleware, AgentMiddleware)
    assert issubclass(ToolErrorHandlingMiddleware, AgentMiddleware)
    assert issubclass(LoopDetectionMiddleware, AgentMiddleware)
