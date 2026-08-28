from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from graph_skill_runtime.core.exceptions import SkillLoadError
from graph_skill_runtime.core.loader import SkillLoader
from graph_skill_runtime.core.manifest import AgentNodeAST, SubgraphNodeAST
from graph_skill_runtime.core.validator_contract import VALIDATOR_ERROR_CODES, VALIDATOR_SIGNATURE

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_portable_graph(
    root: Path,
    *,
    graph_id: str = "root",
    business_skill: bool = True,
) -> None:
    if business_skill:
        _write(
            root / "SKILL.md",
            f"---\nname: {root.name}\ndescription: Gamma contract fixture.\n---\n",
        )
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: {graph_id}
description: Gamma contract graph.
io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    properties: {{}}
phases:
  - id: main
    depends_on: [input]
    output: true
""",
    )


def _write_agent_phase(
    root: Path,
    *,
    validator: bool | None = None,
    include_exit_contract: bool = False,
) -> None:
    validator_line = "" if validator is None else f"validator: {str(validator).lower()}\n"
    exit_contract = (
        """
<exit_contract>
Return via finish_task.
</exit_contract>
"""
        if include_exit_contract
        else ""
    )
    _write(
        root / "phases" / "main" / "AGENT.md",
        f"""---
name: main
{validator_line}
io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    properties: {{}}
---
<role>
Research assistant.
</role>
<goal>
Return a concise answer.
</goal>
<step id="S1" name="Do">
Do the task.
</step>
<protocol id="P1">
Follow the instructions.
</protocol>
{exit_contract}
""",
    )


def _write_subgraph_phase(root: Path, *, validator: bool | None = None) -> None:
    validator_line = "" if validator is None else f"validator: {str(validator).lower()}\n"
    _write(
        root / "phases" / "main" / "SUBGRAPH.md",
        f"""---
name: main
graph: child
io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    properties: {{}}
{validator_line}---
""",
    )


def test_γ0_1_agent_body_without_exit_contract_loads_successfully(tmp_path: Path, mock_skill_resolver: object) -> None:
    root = tmp_path / "gamma-contract"
    _write_portable_graph(root)
    _write_agent_phase(root, include_exit_contract=False)

    compiled = SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    ast = compiled.nodes[0].ast
    assert isinstance(ast, AgentNodeAST)
    assert not hasattr(ast, "exit_contract")


def test_γ0_1_legacy_exit_contract_tag_is_rejected_for_v030_agent(tmp_path: Path, mock_skill_resolver: object) -> None:
    root = tmp_path / "gamma-contract"
    _write_portable_graph(root)
    _write_agent_phase(root, include_exit_contract=True)

    with pytest.raises(SkillLoadError, match="exit_contract"):
        SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)


def test_γ0_2_agent_node_validator_defaults_false() -> None:
    ast = AgentNodeAST.model_validate(
        {
            "mode": "agent",
            "name": "main",
            "role": "Research assistant.",
            "goal": "Return a concise answer.",
            "io": {"inputs": {"type": "object"}, "outputs": {"type": "object"}},
        }
    )

    assert ast.validator is False


def test_γ0_2_agent_loader_accepts_validator_true(tmp_path: Path, mock_skill_resolver: object) -> None:
    root = tmp_path / "gamma-contract"
    _write_portable_graph(root)
    _write_agent_phase(root, validator=True, include_exit_contract=False)

    compiled = SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    ast = compiled.nodes[0].ast
    assert isinstance(ast, AgentNodeAST)
    assert ast.validator is True


def test_validator_non_bool_fatal() -> None:
    with pytest.raises(ValidationError):
        AgentNodeAST.model_validate(
            {
                "mode": "agent",
                "name": "main",
                "role": "Research assistant.",
                "goal": "Return a concise answer.",
                "validator": "maybe",
            }
        )


def test_γ0_2_subgraph_node_validator_defaults_false() -> None:
    ast = SubgraphNodeAST.model_validate(
        {
            "mode": "subgraph",
            "name": "main",
            "graph": "child",
            "io": {"inputs": {"type": "object"}, "outputs": {"type": "object"}},
        }
    )

    assert ast.validator is False


def test_γ0_2_subgraph_loader_accepts_validator_true(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = tmp_path / "gamma-contract"
    _write_portable_graph(root)
    _write_subgraph_phase(root, validator=True)
    child = root / "graphs" / "child"
    _write_portable_graph(child, graph_id="child", business_skill=False)
    _write_agent_phase(child)

    compiled = SkillLoader().compile_skill(root, skill_resolver=mock_skill_resolver)

    ast = compiled.nodes[0].ast
    assert isinstance(ast, SubgraphNodeAST)
    assert ast.validator is True


def test_γ0_3_middleware_order_contract_constant_exists() -> None:
    from graph_skill_runtime import middleware

    assert middleware.MVP0_MIDDLEWARE_ORDER_CONTRACT == (
        "Tracing",
        "ProtocolValidation",
        "CognitiveFlow",
        "ExecutionControl",
        "Compaction",
        "ToolError",
        "LoopDetection",
        "ExitControl",
    )


def test_γ0_4_validator_signature_and_error_placeholders_are_public_constants() -> None:
    assert (
        VALIDATOR_SIGNATURE
        == "def validate(output: dict, state_slice: dict, **kwargs) -> None | dict"
    )
    assert VALIDATOR_ERROR_CODES == (
        "[F-v3-agent-validator-failed]",
        "[F-v3-subgraph-validator-failed]",
        "[F-v3-logic-validator-failed]",
    )


def test_γ0_5_source_contract_matches_public_constants() -> None:
    manifest = (REPO_ROOT / "src/graph_skill_runtime/core/manifest.py").read_text(
        encoding="utf-8"
    )
    middleware_init = (
        REPO_ROOT / "src/graph_skill_runtime/middleware/__init__.py"
    ).read_text(encoding="utf-8")

    assert "class AgentNodeAST" in manifest
    agent_block = manifest.split("class AgentNodeAST", 1)[1].split("class SkillNodeAST", 1)[0]
    if "class SkillNodeAST" not in manifest:
        agent_block = manifest.split("class AgentNodeAST", 1)[1].split("PhaseAST", 1)[0]
    assert "exit_contract" not in agent_block
    assert "validator: StrictBool = False" in agent_block
    assert "MVP0_MIDDLEWARE_ORDER_CONTRACT" in middleware_init
