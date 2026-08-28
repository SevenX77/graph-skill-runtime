"""Capability-probed execution of one provider-neutral AgentTask."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError
from pydantic import JsonValue
from pydantic import ValidationError as PydanticValidationError

from graph_skill_runtime.adapters.process import SubprocessProcessRunner
from graph_skill_runtime.adapters.vendor_cli.vendors import (
    VendorAdapter,
    VendorInvocation,
    VendorName,
    VendorOutputError,
    vendor_adapter,
)
from graph_skill_runtime.domain.models import (
    AgentResult,
    AgentTask,
    CliExecutorConfig,
    JsonObject,
)
from graph_skill_runtime.ports.process import (
    CancellationProbe,
    ProcessCancelledError,
    ProcessOutputLimitError,
    ProcessRequest,
    ProcessResult,
    ProcessRunner,
    ProcessTimedOutError,
)

ExecutableLocator = Callable[[str], str | None]
DispatchCallback = Callable[[], None]
StartedCallback = Callable[[int], None]

_PROBE_TIMEOUT_SECONDS = 10.0
_MAX_RESOURCE_BYTES = 1024 * 1024
_MAX_PROMPT_BYTES = 2 * 1024 * 1024
_MAX_SCHEMA_BYTES = 1024 * 1024

_BASE_ENVIRONMENT_NAMES = frozenset(
    {
        "APPDATA",
        "COLORTERM",
        "COMSPEC",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "LANG",
        "LC_ALL",
        "LOCALAPPDATA",
        "NO_PROXY",
        "PATH",
        "PATHEXT",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "REQUESTS_CA_BUNDLE",
        "SHELL",
        "SSL_CERT_FILE",
        "SYSTEMROOT",
        "TEMP",
        "TERM",
        "TMP",
        "USERPROFILE",
        "WINDIR",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    }
)

_VENDOR_ENVIRONMENT_NAMES: dict[VendorName, frozenset[str]] = {
    "claude": frozenset(
        {
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN",
            "ANTHROPIC_BASE_URL",
            "CLAUDE_CODE_OAUTH_TOKEN",
            "CLAUDE_CONFIG_DIR",
        }
    ),
    "codex": frozenset(
        {
            "AZURE_OPENAI_API_KEY",
            "CODEX_ACCESS_TOKEN",
            "CODEX_API_KEY",
            "CODEX_HOME",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
        }
    ),
    "copilot": frozenset(
        {
            "COPILOT_GITHUB_TOKEN",
            "COPILOT_HOME",
            "GH_HOST",
            "GH_TOKEN",
            "GITHUB_TOKEN",
        }
    ),
    "cursor": frozenset({"CURSOR_API_KEY"}),
    "gemini": frozenset(
        {
            "GEMINI_API_KEY",
            "GEMINI_CLI_HOME",
            "GOOGLE_API_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GOOGLE_CLOUD_LOCATION",
            "GOOGLE_CLOUD_PROJECT",
            "GOOGLE_CLOUD_PROJECT_ID",
            "GOOGLE_GENAI_USE_VERTEXAI",
        }
    ),
    "opencode": frozenset(
        {
            "ANTHROPIC_API_KEY",
            "AWS_ACCESS_KEY_ID",
            "AWS_DEFAULT_REGION",
            "AWS_PROFILE",
            "AWS_REGION",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GROQ_API_KEY",
            "OPENAI_API_KEY",
            "OPENAI_BASE_URL",
            "OPENROUTER_API_KEY",
            "OPENCODE_CONFIG",
            "OPENCODE_CONFIG_DIR",
        }
    ),
}


class CliExecutorUnavailable(RuntimeError):
    """The selected executable cannot prove the required protocol."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        retryable: bool = True,
        details: JsonObject | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retryable = retryable
        self.details = details or {}


class CliExecutorFailure(RuntimeError):
    """A probed CLI attempt failed without consuming its durable AgentTask."""

    def __init__(
        self,
        message: str,
        *,
        category: str,
        retryable: bool,
        details: JsonObject | None = None,
    ) -> None:
        super().__init__(message)
        self.category = category
        self.retryable = retryable
        self.details = details or {}


@dataclass(frozen=True)
class VendorProbe:
    vendor: VendorName
    executable: str
    executable_name: str
    version: str
    capabilities: frozenset[str]
    auth_probe: Literal["verified", "not-exposed"]
    session_persistence: Literal["disabled", "vendor-default"]


def _minimum_environment(vendor: VendorName) -> dict[str, str]:
    allowed = _BASE_ENVIRONMENT_NAMES | _VENDOR_ENVIRONMENT_NAMES[vendor]
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper() in allowed
    }
    environment["NO_COLOR"] = "1"
    environment.setdefault("TERM", "dumb")
    if vendor == "copilot":
        environment.update(
            {
                "COPILOT_AUTO_UPDATE": "false",
                "COPILOT_MCP_TOOL_CACHE": "false",
                "GITHUB_COPILOT_PROMPT_MODE_EXTENSIONS": "false",
                "GITHUB_COPILOT_PROMPT_MODE_REPO_HOOKS": "false",
                "GITHUB_COPILOT_PROMPT_MODE_WORKSPACE_MCP": "false",
            }
        )
    elif vendor == "opencode":
        environment.update(
            {
                "OPENCODE_AUTO_SHARE": "false",
                "OPENCODE_DISABLE_AUTOUPDATE": "true",
                "OPENCODE_DISABLE_CLAUDE_CODE": "true",
                "OPENCODE_DISABLE_DEFAULT_PLUGINS": "true",
                "OPENCODE_DISABLE_LSP_DOWNLOAD": "true",
            }
        )
    return environment


def _first_line(result: ProcessResult) -> str:
    for stream in (result.stdout, result.stderr):
        for line in stream.splitlines():
            if line.strip():
                return line.strip()[:512]
    return "unknown"


def _output_fingerprint(result: ProcessResult) -> str:
    payload = f"{result.stdout}\0{result.stderr}".encode()
    return hashlib.sha256(payload).hexdigest()


def _is_explicit_path(value: str) -> bool:
    return Path(value).is_absolute() or "/" in value or "\\" in value


def _resolve_executable(
    config: CliExecutorConfig,
    adapter: VendorAdapter,
    locator: ExecutableLocator,
) -> str:
    if config.executable is not None:
        requested = config.executable
        if _is_explicit_path(requested) and not Path(requested).is_absolute():
            raise CliExecutorUnavailable(
                f"configured {adapter.name} executable must be a PATH name or absolute path",
                category="invalid-config",
                retryable=False,
            )
        if Path(requested).is_absolute():
            path = Path(requested).expanduser().resolve(strict=False)
            if not path.is_file() or not os.access(path, os.X_OK):
                raise CliExecutorUnavailable(
                    f"configured {adapter.name} executable is not runnable",
                    category="executable-not-found",
                )
            return str(path)
        located = locator(requested)
        if located is None:
            raise CliExecutorUnavailable(
                f"configured {adapter.name} executable was not found on PATH",
                category="executable-not-found",
            )
        return str(Path(located).resolve(strict=False))
    for candidate in adapter.executable_names:
        located = locator(candidate)
        if located is not None:
            return str(Path(located).resolve(strict=False))
    raise CliExecutorUnavailable(
        f"{adapter.name} CLI executable was not found on PATH",
        category="executable-not-found",
    )


def _run_probe_process(
    runner: ProcessRunner,
    argv: tuple[str, ...],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout_seconds: float,
    cancellation: CancellationProbe | None,
) -> ProcessResult:
    try:
        return runner.run(
            ProcessRequest(
                argv=argv,
                cwd=cwd,
                environment=environment,
                stdin=None,
                timeout_seconds=min(_PROBE_TIMEOUT_SECONDS, timeout_seconds),
                max_output_bytes=1024 * 1024,
            ),
            cancellation=cancellation,
        )
    except ProcessCancelledError as exc:
        raise CliExecutorFailure(
            "vendor CLI probe was cancelled",
            category="cancelled",
            retryable=True,
        ) from exc
    except ProcessTimedOutError as exc:
        raise CliExecutorUnavailable(
            "vendor CLI capability probe timed out",
            category="probe-timeout",
        ) from exc
    except (OSError, ProcessOutputLimitError) as exc:
        raise CliExecutorUnavailable(
            "vendor CLI capability probe could not execute",
            category="probe-failed",
        ) from exc


def _resource_is_allowed(path: Path, allowed_paths: tuple[str, ...]) -> bool:
    for raw_allowed in allowed_paths:
        try:
            allowed = Path(raw_allowed).resolve(strict=False)
        except (OSError, RuntimeError, ValueError):
            continue
        if path == allowed or path.is_relative_to(allowed):
            return True
    return False


def _materialized_prompt(task: AgentTask) -> str:
    sections = [
        "This direct CLI task is self-contained. Do not invoke filesystem, shell, "
        "network, MCP, skill, subagent, or other external tools; all authorized "
        "resource contents are included below.",
        task.instructions,
    ]
    total_resource_bytes = 0
    for resource in task.resources:
        declared = Path(resource.path)
        if not declared.is_absolute():
            raise CliExecutorFailure(
                "Agent resource paths must be absolute",
                category="invalid-task",
                retryable=False,
            )
        try:
            path = declared.resolve(strict=True)
        except ValueError as exc:
            raise CliExecutorFailure(
                "an Agent resource path is invalid",
                category="invalid-task",
                retryable=False,
            ) from exc
        except (OSError, RuntimeError) as exc:
            raise CliExecutorFailure(
                "an Agent resource is unavailable",
                category="resource-unavailable",
                retryable=True,
            ) from exc
        if not path.is_file() or not _resource_is_allowed(path, task.allowed_paths):
            raise CliExecutorFailure(
                "an Agent resource is outside its allowed path contract",
                category="invalid-task",
                retryable=False,
            )
        try:
            remaining_bytes = _MAX_RESOURCE_BYTES - total_resource_bytes
            with path.open("rb") as stream:
                payload = stream.read(remaining_bytes + 1)
            if len(payload) > remaining_bytes:
                raise CliExecutorFailure(
                    "declared Agent resources exceed the CLI prompt limit",
                    category="resource-limit",
                    retryable=False,
                )
            content = payload.decode("utf-8-sig")
        except (OSError, UnicodeError) as exc:
            raise CliExecutorFailure(
                "an Agent resource is not readable UTF-8 text",
                category="resource-unavailable",
                retryable=True,
            ) from exc
        total_resource_bytes += len(payload)
        sections.append(
            "\n".join(
                (
                    f"Materialized {resource.kind} @{resource.kind}:{resource.resource_id}",
                    f"Summary: {resource.summary}",
                    "<resource-content>",
                    content,
                    "</resource-content>",
                )
            )
        )
    prompt = "\n\n".join(sections)
    if len(prompt.encode("utf-8")) > _MAX_PROMPT_BYTES:
        raise CliExecutorFailure(
            "Agent task exceeds the CLI prompt limit",
            category="prompt-limit",
            retryable=False,
        )
    return prompt


def _task_timeout(task: AgentTask, configured_timeout: float) -> float:
    if task.deadline is None:
        return configured_timeout
    from datetime import UTC, datetime

    try:
        deadline = datetime.fromisoformat(task.deadline)
        if deadline.tzinfo is None:
            raise ValueError("deadline has no timezone")
    except ValueError as exc:
        raise CliExecutorFailure(
            "AgentTask deadline is not a timezone-aware ISO timestamp",
            category="invalid-task",
            retryable=False,
        ) from exc
    remaining = (deadline.astimezone(UTC) - datetime.now(UTC)).total_seconds()
    if remaining <= 0:
        raise CliExecutorFailure(
            "AgentTask deadline expired before CLI dispatch",
            category="deadline-expired",
            retryable=False,
        )
    return min(configured_timeout, remaining)


def _write_schema(path: Path, schema: JsonObject) -> None:
    payload = json.dumps(
        schema,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    if len(payload.encode("utf-8")) > _MAX_SCHEMA_BYTES:
        raise CliExecutorFailure(
            "AgentTask output_schema exceeds the CLI schema limit",
            category="invalid-task",
            retryable=False,
        )
    path.write_text(payload, encoding="utf-8", newline="\n")


def _write_prompt(path: Path, prompt: str) -> None:
    path.write_text(prompt, encoding="utf-8", newline="\n")


def _run_task_process(
    runner: ProcessRunner,
    invocation: VendorInvocation,
    *,
    workspace: Path,
    environment: dict[str, str],
    timeout_seconds: float,
    cancellation: CancellationProbe | None,
    on_started: StartedCallback | None,
) -> ProcessResult:
    try:
        result = runner.run(
            ProcessRequest(
                argv=invocation.argv,
                cwd=workspace,
                environment=environment,
                stdin=invocation.stdin,
                timeout_seconds=timeout_seconds,
            ),
            cancellation=cancellation,
            on_started=on_started,
        )
    except ProcessCancelledError as exc:
        raise CliExecutorFailure(
            "vendor CLI execution was cancelled",
            category="cancelled",
            retryable=True,
        ) from exc
    except ProcessTimedOutError as exc:
        raise CliExecutorFailure(
            "vendor CLI execution timed out",
            category="timeout",
            retryable=True,
            details={"timeout_seconds": timeout_seconds},
        ) from exc
    except ProcessOutputLimitError as exc:
        raise CliExecutorFailure(
            "vendor CLI output exceeded the runtime limit",
            category="output-limit",
            retryable=True,
        ) from exc
    except OSError as exc:
        raise CliExecutorUnavailable(
            "vendor CLI could not be started after a successful probe",
            category="start-failed",
        ) from exc
    if result.exit_code != 0:
        raise CliExecutorFailure(
            "vendor CLI exited without a valid AgentResult",
            category="nonzero-exit",
            retryable=True,
            details={
                "exit_code": result.exit_code,
                "output_sha256": _output_fingerprint(result),
            },
        )
    return result


def _parse_and_validate_output(
    adapter: VendorAdapter,
    process_result: ProcessResult,
    task: AgentTask,
    *,
    output_path: Path,
) -> tuple[JsonObject, JsonObject]:
    try:
        parsed = adapter.parse_output(process_result, output_path=output_path)
        Draft202012Validator.check_schema(task.output_schema)
        Draft202012Validator(task.output_schema).validate(parsed.output)
    except (VendorOutputError, SchemaError, JsonSchemaValidationError) as exc:
        raise CliExecutorFailure(
            "vendor CLI output did not satisfy the AgentTask JSON Schema",
            category="invalid-output",
            retryable=True,
            details={"output_sha256": _output_fingerprint(process_result)},
        ) from exc
    return parsed.output, parsed.metadata


def _completed_agent_result(
    *,
    task: AgentTask,
    executor_id: str,
    output: JsonObject,
    provenance: JsonObject,
    process_result: ProcessResult,
) -> AgentResult:
    try:
        return AgentResult(
            task_id=task.task_id,
            status="completed",
            output=output,
            executor_id=executor_id,
            provenance=provenance,
        )
    except PydanticValidationError as exc:
        raise CliExecutorFailure(
            "vendor CLI output cannot be represented as a safe AgentResult",
            category="invalid-output",
            retryable=True,
            details={"output_sha256": _output_fingerprint(process_result)},
        ) from exc


def _provenance(
    config: CliExecutorConfig,
    probe: VendorProbe,
    process_result: ProcessResult,
    metadata: JsonObject,
) -> JsonObject:
    value: JsonObject = {
        "auth_probe": probe.auth_probe,
        "capabilities": cast(JsonValue, sorted(probe.capabilities)),
        "duration_ms": int(process_result.duration_seconds * 1000),
        "executable_name": probe.executable_name,
        "fresh_top_level_session": True,
        "session_persistence": probe.session_persistence,
        "vendor": probe.vendor,
        "version": probe.version,
        **metadata,
    }
    if config.agent_profile is not None:
        value["requested_agent_profile"] = config.agent_profile
    if config.model_override is not None:
        value["requested_model"] = config.model_override
    return value


class VendorCliExecutor:
    """Probe one vendor protocol and execute tasks through fresh CLI sessions."""

    def __init__(
        self,
        config: CliExecutorConfig,
        *,
        process_runner: ProcessRunner | None = None,
        executable_locator: ExecutableLocator = shutil.which,
        cancellation: CancellationProbe | None = None,
    ) -> None:
        self._config = config
        self._adapter = vendor_adapter(config.vendor)
        self._runner = process_runner or SubprocessProcessRunner()
        self._locator = executable_locator
        self._cancellation = cancellation

    @property
    def executor_id(self) -> str:
        return f"gskill-cli:{self._config.vendor}"

    def probe(self) -> VendorProbe:
        adapter = self._adapter
        if self._config.agent_profile is not None and "agent-profile" not in adapter.capabilities:
            raise CliExecutorUnavailable(
                f"{adapter.name} CLI cannot select an agent profile",
                category="capability-missing",
                retryable=False,
                details={"capability": "agent-profile"},
            )
        executable = _resolve_executable(self._config, adapter, self._locator)
        environment = _minimum_environment(adapter.name)
        with tempfile.TemporaryDirectory(prefix="gskill-cli-probe-") as raw_workspace:
            workspace = Path(raw_workspace).resolve()
            version_result = _run_probe_process(
                self._runner,
                (executable, "--version"),
                cwd=workspace,
                environment=environment,
                timeout_seconds=self._config.timeout_seconds,
                cancellation=self._cancellation,
            )
            if version_result.exit_code != 0:
                raise CliExecutorUnavailable(
                    f"{adapter.name} CLI version probe failed",
                    category="version-probe-failed",
                    details={
                        "exit_code": version_result.exit_code,
                        "output_sha256": _output_fingerprint(version_result),
                    },
                )
            version = _first_line(version_result)
            for help_probe in adapter.help_probes(executable, self._config):
                help_result = _run_probe_process(
                    self._runner,
                    help_probe.argv,
                    cwd=workspace,
                    environment=environment,
                    timeout_seconds=self._config.timeout_seconds,
                    cancellation=self._cancellation,
                )
                if help_result.exit_code != 0:
                    raise CliExecutorUnavailable(
                        f"{adapter.name} CLI help probe failed",
                        category="help-probe-failed",
                        details={"exit_code": help_result.exit_code},
                    )
                help_text = f"{help_result.stdout}\n{help_result.stderr}"
                missing = sorted(
                    flag
                    for flag in help_probe.required_flags
                    if flag not in help_text
                )
                if missing:
                    raise CliExecutorUnavailable(
                        f"{adapter.name} CLI lacks required non-interactive capabilities",
                        category="capability-missing",
                        details={"missing_flags": cast(JsonValue, missing)},
                    )
            auth_argv = adapter.auth_argv(executable)
            auth_probe: Literal["verified", "not-exposed"] = "not-exposed"
            if auth_argv is not None:
                auth_result = _run_probe_process(
                    self._runner,
                    auth_argv,
                    cwd=workspace,
                    environment=environment,
                    timeout_seconds=self._config.timeout_seconds,
                    cancellation=self._cancellation,
                )
                if not adapter.auth_succeeded(auth_result):
                    raise CliExecutorUnavailable(
                        f"{adapter.name} CLI is not authenticated",
                        category="authentication-missing",
                        details={"exit_code": auth_result.exit_code},
                    )
                auth_probe = "verified"
        return VendorProbe(
            vendor=adapter.name,
            executable=executable,
            executable_name=Path(executable).name,
            version=version,
            capabilities=adapter.capabilities,
            auth_probe=auth_probe,
            session_persistence=adapter.session_persistence,
        )

    def execute(
        self,
        task: AgentTask,
        probe: VendorProbe | None = None,
        *,
        on_dispatched: DispatchCallback | None = None,
        on_started: StartedCallback | None = None,
    ) -> AgentResult:
        active_probe = probe or self.probe()
        if active_probe.vendor != self._config.vendor:
            raise CliExecutorFailure(
                "vendor probe does not match the executor configuration",
                category="invalid-probe",
                retryable=False,
            )
        try:
            Draft202012Validator.check_schema(task.output_schema)
        except SchemaError as exc:
            raise CliExecutorFailure(
                "AgentTask output_schema is not a valid JSON Schema",
                category="invalid-task",
                retryable=False,
            ) from exc
        prompt = _materialized_prompt(task)
        environment = _minimum_environment(active_probe.vendor)
        timeout_seconds = _task_timeout(task, self._config.timeout_seconds)

        with tempfile.TemporaryDirectory(
            prefix=f"gskill-{active_probe.vendor}-"
        ) as raw_workspace:
            workspace = Path(raw_workspace).resolve()
            prompt_path = workspace / "agent-task.md"
            schema_path = workspace / "output-schema.json"
            output_path = workspace / "final-response.json"
            _write_prompt(prompt_path, prompt)
            _write_schema(schema_path, task.output_schema)
            invocation = self._adapter.build_invocation(
                active_probe.executable,
                self._config,
                prompt=prompt,
                workspace=workspace,
                prompt_path=prompt_path,
                schema_path=schema_path,
                output_path=output_path,
            )
            if on_dispatched is not None:
                on_dispatched()
            process_result = _run_task_process(
                self._runner,
                invocation,
                workspace=workspace,
                environment=environment,
                timeout_seconds=timeout_seconds,
                cancellation=self._cancellation,
                on_started=on_started,
            )
            output, metadata = _parse_and_validate_output(
                self._adapter,
                process_result,
                task,
                output_path=output_path,
            )
            metadata = {
                **metadata,
                "schema_enforcement": invocation.schema_enforcement,
            }
            return _completed_agent_result(
                task=task,
                executor_id=self.executor_id,
                output=output,
                provenance=_provenance(
                    self._config, active_probe, process_result, metadata
                ),
                process_result=process_result,
            )
