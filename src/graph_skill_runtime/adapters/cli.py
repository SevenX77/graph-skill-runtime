"""Stable ``gskill`` console adapter over :class:`RuntimeApplication`."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version

from pydantic import BaseModel, TypeAdapter, ValidationError

from graph_skill_runtime.application.config import ConfigurationError
from graph_skill_runtime.application.service import RuntimeApplication
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
    vendor = getattr(args, "vendor", None)
    if vendor is not None and executor_kind != "cli":
        raise ValueError("--vendor requires --executor=cli")
    if executor_kind is None:
        return RuntimeProfileOverlay(state_dir=state_dir)
    executor: ExecutorConfig
    if executor_kind == "host-native":
        executor = HostNativeExecutorConfig()
    elif executor_kind == "embedded":
        executor = EmbeddedExecutorConfig()
    else:
        if vendor is None:
            raise ValueError("--vendor is required when --executor=cli")
        executor = CliExecutorConfig(vendor=vendor)
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


def _exit_code(model: BaseModel) -> int:
    status = getattr(model, "status", None)
    if status == "failed":
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
    parser.add_argument("--inputs-json", help="Non-secret business inputs as a JSON object")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gskill", description="Compile and run provider-neutral graph skills"
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {_package_version()}")
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

    commands.add_parser("mcp", help="Serve gskill tools over MCP stdio")
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


def main(
    argv: Sequence[str] | None = None,
    *,
    application: RuntimeApplication | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    active_application = application or create_application()
    if args.command == "mcp":
        from graph_skill_runtime.adapters.mcp import create_server

        create_server(active_application).run("stdio")
        return 0
    if args.command == "migrate" and args.migrate_command == "studio-skill":
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
    try:
        result = _dispatch(args, active_application)
    except MigrationFailure as exc:
        _write_model(exc.report)
        return 2
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
