from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from graph_skill_runtime.adapters.cli import build_parser
from graph_skill_runtime.adapters.cli import main as cli_main
from graph_skill_runtime.agent_kit.catalog import PackagedAgentKitAssets
from graph_skill_runtime.agent_kit.guide import agent_configuration_guide
from graph_skill_runtime.domain.models import (
    CompileRequest,
    GoldenEvaluationRequest,
    InspectRequest,
    PredictRequest,
    ResumeRequest,
    RunInvocation,
    SubmitAgentResultRequest,
)
from graph_skill_runtime.gskill_version import GSKILL_SCHEMA_VERSION

EXPECTED_RULES = (
    "00-index.md",
    "01-identification-and-version.md",
    "02-entrypoints.md",
    "03-skill-routing.md",
    "04-authoring.md",
    "05-agent-handoff.md",
    "06-configuration-and-state.md",
    "07-diagnostics-and-repair.md",
    "08-execution-and-evidence.md",
    "09-safety-and-boundaries.md",
)
CANONICAL_CHILD_PROMPT = (
    "You execute exactly one gSkill AgentTask in a fresh context. Treat the supplied "
    "AgentTask as the complete task contract. Do not run, resume, or modify the parent "
    "graph. Use only capabilities, tools, paths, and network access allowed by the task "
    "and the current host policy. Return exactly one JSON object that satisfies "
    "task.output_schema, without Markdown or commentary. If the task cannot be completed "
    "within those constraints, report failure to the parent instead of inventing output."
)


def test_packaged_agent_kit_is_closed_and_uses_two_precise_skills() -> None:
    assets = PackagedAgentKitAssets()

    assert assets.gskill_version == GSKILL_SCHEMA_VERSION
    assert assets.skill_ids() == ("gskill", "create-gskill")
    assert tuple(name for name, _content in assets.rule_files()) == EXPECTED_RULES
    assert tuple(name for name, _content in assets.skill_reference_files("gskill")) == (
        EXPECTED_RULES[1:]
    )
    assert tuple(
        name for name, _content in assets.skill_reference_files("create-gskill")
    ) == (
        "01-identification-and-version.md",
        "02-entrypoints.md",
        "03-skill-routing.md",
        "04-authoring.md",
        "07-diagnostics-and-repair.md",
        "09-safety-and-boundaries.md",
    )
    assert b"metadata.gskill: gskill.graph.v1" in assets.skill_file("gskill")
    create_skill = assets.skill_file("create-gskill").decode("utf-8").casefold()
    assert "ordinary non-graph agent skill" in create_skill


def test_packaged_skills_link_exactly_their_local_reference_subsets() -> None:
    assets = PackagedAgentKitAssets()

    for skill_id in assets.skill_ids():
        body = assets.skill_file(skill_id).decode("utf-8")
        linked = tuple(re.findall(r"\(references/([^)]+\.md)\)", body))
        installed = tuple(
            name for name, _content in assets.skill_reference_files(skill_id)
        )
        assert len(linked) == len(set(linked)) == len(installed)
        assert set(linked) == set(installed)


def test_shared_entrypoint_reference_covers_the_complete_module_cli() -> None:
    assets = PackagedAgentKitAssets()
    rules = dict(assets.rule_files())
    manual = rules["02-entrypoints.md"].decode("utf-8")
    command_heads = (
        "python -m graph_skill_runtime --version",
        "python -m graph_skill_runtime compile ",
        "python -m graph_skill_runtime config resolve ",
        "python -m graph_skill_runtime predict ",
        "python -m graph_skill_runtime run ",
        "python -m graph_skill_runtime resume ",
        "python -m graph_skill_runtime submit ",
        "python -m graph_skill_runtime inspect ",
        "python -m graph_skill_runtime golden ",
        "python -m graph_skill_runtime migrate studio-skill ",
        "python -m graph_skill_runtime integrations detect",
        "python -m graph_skill_runtime integrations install moirai ",
        "python -m graph_skill_runtime integrations uninstall moirai ",
        "python -m graph_skill_runtime mcp",
        "python -m graph_skill_runtime guide agent-configuration",
        "python -m graph_skill_runtime create ",
    )
    options = (
        "--no-cache",
        "--run-id",
        "--preset",
        "--state-dir",
        "--executor",
        "--vendor",
        "--agent-profile",
        "--model",
        "--executable",
        "--timeout-seconds",
        "--inputs-json",
        "--state-root",
        "--checkpoint-ref",
        "--human-response-json",
        "--result-json",
        "--call-graph",
        "--runtime-config",
        "--preset-id",
        "--targets",
        "--scope",
        "--project-root",
        "--dry-run",
        "--path",
        "--description",
    )

    for command in command_heads:
        assert command in manual
    for option in options:
        assert option in manual
    documented_commands = tuple(
        line for line in manual.splitlines() if line.startswith(("python ", "gskill ", "uv "))
    )
    assert documented_commands
    assert all(
        command.startswith("python -m graph_skill_runtime")
        for command in documented_commands
    )
    assert "python -m graph_skill_runtime setup" not in manual
    assert "guide agent-setup" not in manual
    assert "uv tool install" in manual
    assert "is not the installation form" in manual


def test_shared_entrypoint_reference_covers_exact_mcp_argument_envelopes() -> None:
    assets = PackagedAgentKitAssets()
    manual = dict(assets.rule_files())["02-entrypoints.md"].decode("utf-8")
    tool_names = (
        "compile",
        "resolve_run",
        "predict",
        "run",
        "resume",
        "submit_agent_result",
        "inspect",
        "evaluate_golden",
    )
    envelopes = {
        tool_name: json.loads(
            next(
                line.split(": ", maxsplit=1)[1]
                for line in manual.splitlines()
                if line.startswith(f"{tool_name}: ")
            )
        )
        for tool_name in tool_names
    }
    normalized = json.loads(
        json.dumps(envelopes)
        .replace("SKILL_ROOT", "C:/skill")
        .replace("STATE_ROOT", "C:/state")
        .replace("BASELINE_ID", "baseline-a")
        .replace("RUN_ID", "run-1")
        .replace("TASK_ID", "task-1")
        .replace("HOST_NATIVE", "host-native")
        .replace("REF", "checkpoint-1")
    )

    CompileRequest.model_validate(normalized["compile"]["request"])
    RunInvocation.model_validate(normalized["resolve_run"]["invocation"])
    PredictRequest.model_validate(normalized["predict"]["request"])
    RunInvocation.model_validate(normalized["run"]["invocation"])
    ResumeRequest.model_validate(normalized["resume"]["request"])
    SubmitAgentResultRequest.model_validate(
        normalized["submit_agent_result"]["request"]
    )
    InspectRequest.model_validate(normalized["inspect"]["request"])
    GoldenEvaluationRequest.model_validate(normalized["evaluate_golden"]["request"])
    assert "request` or `invocation`" in manual
    assert "never submit the literal placeholders" in manual


def test_canonical_child_prompt_has_one_owner_and_kit_is_provider_neutral() -> None:
    assets = PackagedAgentKitAssets()
    documents = {
        "AGENTS.md": assets.agents_template().decode("utf-8"),
        **{
            f"rules/{name}": content.decode("utf-8")
            for name, content in assets.rule_files()
        },
        **{
            f"skills/{skill_id}/SKILL.md": assets.skill_file(skill_id).decode("utf-8")
            for skill_id in assets.skill_ids()
        },
    }

    assert sum(text.count(CANONICAL_CHILD_PROMPT) for text in documents.values()) == 1
    assert CANONICAL_CHILD_PROMPT in documents["rules/05-agent-handoff.md"]
    provider_neutral = "\n".join(
        text
        for name, text in documents.items()
        if name != "rules/02-entrypoints.md"
    ).casefold()
    for provider in ("claude", "codex", "copilot", "cursor", "gemini", "opencode"):
        assert provider not in provider_neutral
        assert provider in documents["rules/02-entrypoints.md"].casefold()


def test_mandatory_agent_handoff_is_serial_bounded_and_pre_authorized() -> None:
    assets = PackagedAgentKitAssets()
    rules = dict(assets.rule_files())
    handoff = rules["05-agent-handoff.md"].decode("utf-8")
    agents = assets.agents_template().decode("utf-8")
    gskill_references = dict(assets.skill_reference_files("gskill"))

    assert gskill_references["05-agent-handoff.md"] == rules["05-agent-handoff.md"]
    assert "run authorization includes exactly one" in handoff
    assert "for each serial `agent_required` boundary" in handoff
    assert "does not ask again at every wait" in handoff
    assert "not optional parallel delegation" in handoff
    assert "does not authorize an extra or parallel child" in handoff
    assert "further subagents created by the child" in handoff
    assert "explicitly prohibited a native child for this specific gSkill run" in handoff
    assert "unavoidable host policy still applies" in handoff
    assert "A general restriction on optional or parallel development subagents" in agents


def test_agent_configuration_guide_contains_canonical_sources_without_destinations() -> None:
    assets = PackagedAgentKitAssets()

    result = agent_configuration_guide(assets=assets)
    files = {asset.relative_path: asset for asset in result.assets}

    assert result.status == "guidance"
    assert result.writes_performed is False
    assert tuple(placement.host for placement in result.placements) == (
        "codex",
        "claude-code",
        "other",
    )
    assert "AGENTS.md" in files
    for name, content in assets.rule_files():
        rule_path = f"rules/{name}"
        assert files[rule_path].content.encode("utf-8") == content
    for skill_id in assets.skill_ids():
        skill_path = f"skills/{skill_id}/SKILL.md"
        assert files[skill_path].content.encode("utf-8") == assets.skill_file(skill_id)
    for asset in result.assets:
        assert asset.sha256 == hashlib.sha256(asset.content.encode("utf-8")).hexdigest()
    assert not any(asset.relative_path.startswith(("~", "$", "/")) for asset in result.assets)


def test_agent_configuration_guide_requires_user_choice_and_additive_merge() -> None:
    result = agent_configuration_guide()
    decisions = "\n".join(result.decisions).casefold()

    assert "which hosts" in decisions
    assert "user or one project" in decisions
    assert "manually or authorizes" in decisions
    assert "never replace" in decisions
    assert "write only after" in decisions


def test_agent_configuration_cli_is_read_only_even_in_an_empty_project(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    exit_code = cli_main(["guide", "agent-configuration"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "guidance"
    assert payload["writes_performed"] is False
    assert tuple(tmp_path.iterdir()) == ()


def test_removed_setup_command_cannot_mutate_a_project(tmp_path: Path) -> None:
    parser = build_parser()

    with pytest.raises(SystemExit) as raised:
        parser.parse_args(["setup", str(tmp_path)])

    assert raised.value.code == 2
    assert tuple(tmp_path.iterdir()) == ()
