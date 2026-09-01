"""Stable module CLI adapter over :class:`RuntimeApplication`."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from pydantic import BaseModel, TypeAdapter, ValidationError

from graph_skill_runtime.agent_kit.guide import agent_configuration_guide
from graph_skill_runtime.application.config import ConfigurationError
from graph_skill_runtime.application.service import RuntimeApplication
from graph_skill_runtime.authoring.scaffold import create_gskill
from graph_skill_runtime.composition import create_application
from graph_skill_runtime.domain.models import (
    AgentResult,
    CliExecutorConfig,
    CompileRequest,
    EmbeddedExecutorConfig,
    ExecutorConfig,
    GoldenEvaluationRequest,
    HostNativeExecutorConfig,
    InspectRequest,
    JsonObject,
    PredictRequest,
    ResumeRequest,
    RunInvocation,
    RuntimeErrorCode,
    RuntimeErrorPayload,
    RuntimeProfileOverlay,
    SubmitAgentResultRequest,
)
from graph_skill_runtime.gskill_version import GSKILL_SCHEMA_VERSION
from graph_skill_runtime.integrations.installer import IntegrationInstaller
from graph_skill_runtime.integrations.models import (
    HostDetectionResult,
    IntegrationRequest,
    IntegrationResult,
    IntegrationScope,
    IntegrationTarget,
)
from graph_skill_runtime.migration import MigrationFailure

_JSON_OBJECT_ADAPTER = TypeAdapter(JsonObject)


def _package_version() -> str:
    try:
        return version("graph-skill-runtime")
    except PackageNotFoundError:
        return "0+unknown"


def _json_object(raw: str | None, *, option: str) -> JsonObject | None:
    if raw is None:
        return None
    try:
        decoded = json.loads(raw)
        return _JSON_OBJECT_ADAPTER.validate_python(decoded)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"{option} must be a JSON object: {exc}") from exc


def _executor(args: argparse.Namespace) -> RuntimeProfileOverlay:
    executor_kind = getattr(args, "executor", None)
    state_dir = getattr(args, "state_dir", None)
    cli_options = (
        ("vendor", "--vendor"),
        ("agent_profile", "--agent-profile"),
        ("model", "--model"),
        ("executable", "--executable"),
        ("timeout_seconds", "--timeout-seconds"),
    )
    for attribute, option in cli_options:
        if getattr(args, attribute, None) is not None and executor_kind != "cli":
            raise ValueError(f"{option} requires --executor=cli")
    if executor_kind is None:
        return RuntimeProfileOverlay(state_dir=state_dir)
    executor: ExecutorConfig
    if executor_kind == "host-native":
        executor = HostNativeExecutorConfig()
    elif executor_kind == "embedded":
        executor = EmbeddedExecutorConfig()
    else:
        vendor = getattr(args, "vendor", None)
        if vendor is None:
            raise ValueError("--vendor is required when --executor=cli")
        timeout_seconds = getattr(args, "timeout_seconds", None)
        executor = CliExecutorConfig(
            vendor=vendor,
            agent_profile=getattr(args, "agent_profile", None),
            model_override=getattr(args, "model", None),
            executable=getattr(args, "executable", None),
            timeout_seconds=600.0 if timeout_seconds is None else timeout_seconds,
        )
    return RuntimeProfileOverlay(executor=executor, state_dir=state_dir)


def _invocation(args: argparse.Namespace) -> RunInvocation:
    return RunInvocation(
        skill_root=args.skill_root,
        run_id=getattr(args, "run_id", None),
        preset_id=getattr(args, "preset", None),
        runtime=_executor(args),
        inputs=_json_object(getattr(args, "inputs_json", None), option="--inputs-json"),
    )


def _write_model(model: BaseModel) -> None:
    sys.stdout.write(model.model_dump_json(indent=2) + "\n")


def _configure_standard_streams_as_utf8() -> None:
    """Keep the JSON transport encoding stable across host console code pages."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="strict")


def _exit_code(model: BaseModel) -> int:
    status = getattr(model, "status", None)
    if status in {"failed", "conflict"}:
        return 2
    passed = getattr(model, "passed", None)
    if passed is False:
        return 2
    return 0


def _add_invocation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("skill_root")
    parser.add_argument("--run-id")
    parser.add_argument("--preset")
    parser.add_argument("--state-dir")
    parser.add_argument(
        "--executor",
        choices=("host-native", "cli", "embedded"),
        help="Explicit executor selection; defaults to host-native",
    )
    parser.add_argument(
        "--vendor",
        choices=("claude", "codex", "copilot", "cursor", "gemini", "opencode"),
    )
    parser.add_argument(
        "--agent-profile",
        help="Vendor-native agent selector (Copilot, Gemini, or OpenCode only)",
    )
    parser.add_argument("--model", help="Vendor-native model identifier")
    parser.add_argument("--executable", help="CLI executable name or absolute path")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        help="Maximum wall time for each vendor Agent process",
    )
    parser.add_argument("--inputs-json", help="Non-secret business inputs as a JSON object")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m graph_skill_runtime",
        description="Compile and run provider-neutral graph skills",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=(
            f"%(prog)s {GSKILL_SCHEMA_VERSION} "
            f"(graph-skill-runtime {_package_version()})"
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    compile_parser = commands.add_parser("compile", help="Compile a graph skill")
    compile_parser.add_argument("skill_root")
    compile_parser.add_argument("--no-cache", action="store_true")

    config_parser = commands.add_parser("config", help="Resolve runtime configuration")
    config_commands = config_parser.add_subparsers(dest="config_command", required=True)
    resolve_parser = config_commands.add_parser("resolve", help="Print one immutable run request")
    _add_invocation_arguments(resolve_parser)

    predict_parser = commands.add_parser("predict", help="Predict a run with deterministic stubs")
    _add_invocation_arguments(predict_parser)

    run_parser = commands.add_parser("run", help="Execute a graph skill")
    _add_invocation_arguments(run_parser)

    resume_parser = commands.add_parser("resume", help="Resume a durable run")
    resume_parser.add_argument("skill_root")
    resume_parser.add_argument("run_id")
    resume_parser.add_argument("--state-root", required=True)
    resume_parser.add_argument("--checkpoint-ref")
    resume_parser.add_argument("--human-response-json")

    submit_parser = commands.add_parser("submit", help="Submit a host-native agent result")
    submit_parser.add_argument("run_id")
    submit_parser.add_argument("--state-root", required=True)
    submit_parser.add_argument("--checkpoint-ref", required=True)
    submit_parser.add_argument("--result-json", required=True)

    inspect_parser = commands.add_parser("inspect", help="Inspect compiled topology")
    inspect_parser.add_argument("skill_root")
    inspect_parser.add_argument("--call-graph", action="store_true")

    golden_parser = commands.add_parser("golden", help="Evaluate a golden baseline")
    golden_parser.add_argument("skill_root")
    golden_parser.add_argument("baseline_id")
    golden_parser.add_argument("--state-root", required=True)

    migrate_parser = commands.add_parser("migrate", help="Run an explicit one-shot format converter")
    migrate_commands = migrate_parser.add_subparsers(dest="migrate_command", required=True)
    studio_parser = migrate_commands.add_parser(
        "studio-skill", help="Convert a frozen Studio v0.3 skill to portable v1"
    )
    studio_parser.add_argument("source")
    studio_parser.add_argument("destination")
    studio_parser.add_argument("--runtime-config")
    studio_parser.add_argument("--preset-id", default="migrated")

    integrations_parser = commands.add_parser(
        "integrations", help="Project optional assets into supported agent hosts"
    )
    integration_commands = integrations_parser.add_subparsers(
        dest="integrations_command", required=True
    )
    integration_commands.add_parser(
        "detect", help="Report supported host executables found on PATH"
    )
    for operation in ("install", "uninstall"):
        operation_parser = integration_commands.add_parser(
            operation,
            help=f"{operation.capitalize()} one manifest-owned host projection",
        )
        operation_parser.add_argument("integration_id", choices=("moirai",))
        operation_parser.add_argument(
            "--targets",
            required=True,
            help="Comma-separated host names or the single value 'detected'",
        )
        operation_parser.add_argument(
            "--scope",
            choices=("user", "project"),
            required=True,
        )
        operation_parser.add_argument(
            "--project-root",
            help="Project root; defaults to the current directory for project scope",
        )
        operation_parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Plan and detect conflicts without writing host state",
        )

    commands.add_parser("mcp", help="Serve gskill tools over MCP stdio")

    guide_parser = commands.add_parser(
        "guide", help="Read provider-neutral configuration guidance without writing"
    )
    guide_commands = guide_parser.add_subparsers(dest="guide_command", required=True)
    guide_commands.add_parser(
        "agent-configuration",
        help="Explain user/project instruction and Skill placement choices",
    )

    create_parser = commands.add_parser("create", help="Create one minimal portable gSkill")
    create_parser.add_argument("name")
    create_parser.add_argument("--path", required=True, help="Existing parent directory")
    create_parser.add_argument(
        "--description",
        required=True,
        help="Business purpose and activation conditions for the new gSkill",
    )
    return parser


def _dispatch(args: argparse.Namespace, application: RuntimeApplication) -> BaseModel:
    if args.command == "compile":
        return application.compile(
            CompileRequest(skill_root=args.skill_root, cache=not args.no_cache)
        )
    if args.command == "config" and args.config_command == "resolve":
        return application.resolve_run(_invocation(args))
    if args.command == "predict":
        return application.predict(PredictRequest(invocation=_invocation(args)))
    if args.command == "run":
        return application.run(_invocation(args))
    if args.command == "resume":
        return application.resume(
            ResumeRequest(
                skill_root=args.skill_root,
                run_id=args.run_id,
                state_root=args.state_root,
                checkpoint_ref=args.checkpoint_ref,
                human_response=_json_object(
                    args.human_response_json, option="--human-response-json"
                ),
            )
        )
    if args.command == "submit":
        try:
            result = AgentResult.model_validate_json(args.result_json)
        except ValidationError as exc:
            raise ValueError(f"--result-json is not a valid AgentResult: {exc}") from exc
        return application.submit_agent_result(
            SubmitAgentResultRequest(
                run_id=args.run_id,
                state_root=args.state_root,
                checkpoint_ref=args.checkpoint_ref,
                result=result,
            )
        )
    if args.command == "inspect":
        return application.inspect(
            InspectRequest(
                skill_root=args.skill_root,
                include_call_graph=bool(args.call_graph),
            )
        )
    if args.command == "golden":
        return application.evaluate_golden(
            GoldenEvaluationRequest(
                skill_root=args.skill_root,
                state_root=args.state_root,
                baseline_id=args.baseline_id,
            )
        )
    raise ValueError(f"unknown command: {args.command}")


def _integration_targets(
    raw: str,
    *,
    installer: IntegrationInstaller,
) -> tuple[IntegrationTarget, ...]:
    values = tuple(part.strip() for part in raw.split(",") if part.strip())
    if values == ("detected",):
        targets = installer.detected_targets()
        if not targets:
            raise ValueError(
                "no supported host executables were detected; pass explicit --targets"
            )
        return targets
    if "detected" in values:
        raise ValueError("'detected' cannot be mixed with explicit target names")
    if not values:
        raise ValueError("--targets must contain at least one host")
    try:
        return tuple(IntegrationTarget(value) for value in values)
    except ValueError as exc:
        supported = ", ".join(target.value for target in IntegrationTarget)
        raise ValueError(f"unsupported integration target; choose one of: {supported}") from exc


def _integration_request(
    args: argparse.Namespace,
    *,
    installer: IntegrationInstaller,
) -> IntegrationRequest:
    scope = IntegrationScope(args.scope)
    project_root = args.project_root
    if scope is IntegrationScope.PROJECT and project_root is None:
        project_root = str(Path.cwd())
    return IntegrationRequest(
        integration_id=args.integration_id,
        targets=_integration_targets(args.targets, installer=installer),
        scope=scope,
        project_root=project_root,
    )


def _run_integration_command(
    args: argparse.Namespace,
    *,
    installer: IntegrationInstaller,
) -> BaseModel:
    if args.integrations_command == "detect":
        return HostDetectionResult(detections=installer.detect_hosts())
    request = _integration_request(args, installer=installer)
    if args.integrations_command == "install":
        if args.dry_run:
            plan = installer.plan_install(request)
            return IntegrationResult(
                status="planned" if plan.can_apply else "conflict",
                plan=plan,
                applied_changes=0,
            )
        return installer.install(request)
    if args.dry_run:
        plan = installer.plan_uninstall(request)
        return IntegrationResult(
            status="planned" if plan.can_apply else "conflict",
            plan=plan,
            applied_changes=0,
        )
    return installer.uninstall(request)


def _run_authoring_command(args: argparse.Namespace) -> BaseModel:
    return create_gskill(
        args.name,
        parent=args.path,
        description=args.description,
    )


def _handle_authoring_command(args: argparse.Namespace) -> int:
    try:
        result = _run_authoring_command(args)
    except (OSError, ValueError, ValidationError) as exc:
        _write_model(
            RuntimeErrorPayload(
                code=RuntimeErrorCode.INVALID_REQUEST,
                message=str(exc),
            )
        )
        return 2
    _write_model(result)
    return _exit_code(result)


def _handle_migration_command(args: argparse.Namespace) -> int:
    from graph_skill_runtime.migration import migrate_studio_skill

    try:
        migration = migrate_studio_skill(
            args.source,
            args.destination,
            runtime_config=args.runtime_config,
            preset_id=args.preset_id,
        )
    except MigrationFailure as exc:
        _write_model(exc.report)
        return 2
    _write_model(migration)
    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    application: RuntimeApplication | None = None,
    integration_installer: IntegrationInstaller | None = None,
) -> int:
    _configure_standard_streams_as_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "integrations":
        try:
            result = _run_integration_command(
                args,
                installer=integration_installer or IntegrationInstaller(),
            )
        except (ValueError, ValidationError) as exc:
            _write_model(
                RuntimeErrorPayload(
                    code=RuntimeErrorCode.INVALID_REQUEST,
                    message=str(exc),
                )
            )
            return 2
        except (OSError, RuntimeError) as exc:
            _write_model(
                RuntimeErrorPayload(
                    code=RuntimeErrorCode.INTERNAL_ERROR,
                    message=str(exc),
                )
            )
            return 2
        _write_model(result)
        return _exit_code(result)
    if args.command == "mcp":
        active_application = application or create_application()
        from graph_skill_runtime.adapters.mcp import create_server

        create_server(active_application).run("stdio")
        return 0
    if args.command == "migrate" and args.migrate_command == "studio-skill":
        return _handle_migration_command(args)
    if args.command == "guide" and args.guide_command == "agent-configuration":
        _write_model(agent_configuration_guide())
        return 0
    if args.command == "create":
        return _handle_authoring_command(args)
    active_application = application or create_application()
    try:
        result = _dispatch(args, active_application)
    except ConfigurationError as exc:
        _write_model(exc.payload)
        return 2
    except (OSError, ValueError, ValidationError) as exc:
        _write_model(
            RuntimeErrorPayload(
                code=RuntimeErrorCode.INVALID_REQUEST,
                message=str(exc),
            )
        )
        return 2
    _write_model(result)
    return _exit_code(result)
