"""Version-probed command builders and output parsers for supported CLIs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, TypeAlias, cast

from pydantic import JsonValue, TypeAdapter, ValidationError

from graph_skill_runtime.domain.models import CliExecutorConfig, JsonObject
from graph_skill_runtime.ports.process import ProcessResult

VendorName: TypeAlias = Literal[
    "claude", "codex", "copilot", "cursor", "gemini", "opencode"
]

_JSON_OBJECT = TypeAdapter(JsonObject)
_MAX_INLINE_SCHEMA_BYTES = 12 * 1024
_MAX_FINAL_RESPONSE_BYTES = 4 * 1024 * 1024
_BASE_CAPABILITIES = frozenset(
    {
        "cancellation",
        "declared-resources",
        "fresh-top-level-session",
        "structured-output",
        "timeout",
    }
)


class VendorOutputError(ValueError):
    """A successful process did not satisfy its documented output contract."""


@dataclass(frozen=True)
class VendorInvocation:
    argv: tuple[str, ...]
    stdin: str | None
    schema_enforcement: Literal["vendor-native+runtime", "runtime"]


@dataclass(frozen=True)
class ParsedVendorOutput:
    output: JsonObject
    metadata: JsonObject


@dataclass(frozen=True)
class VendorHelpProbe:
    argv: tuple[str, ...]
    required_flags: frozenset[str]


class VendorAdapter(Protocol):
    @property
    def name(self) -> VendorName: ...

    @property
    def executable_names(self) -> tuple[str, ...]: ...

    @property
    def capabilities(self) -> frozenset[str]: ...

    @property
    def session_persistence(self) -> Literal["disabled", "vendor-default"]: ...

    def help_probes(
        self,
        executable: str,
        config: CliExecutorConfig,
    ) -> tuple[VendorHelpProbe, ...]: ...

    def auth_argv(self, executable: str) -> tuple[str, ...] | None: ...

    def auth_succeeded(self, result: ProcessResult) -> bool: ...

    def build_invocation(
        self,
        executable: str,
        config: CliExecutorConfig,
        *,
        prompt: str,
        workspace: Path,
        prompt_path: Path,
        schema_path: Path,
        output_path: Path,
    ) -> VendorInvocation: ...

    def parse_output(
        self,
        result: ProcessResult,
        *,
        output_path: Path,
    ) -> ParsedVendorOutput: ...


def _decode_json(raw: str, *, label: str) -> JsonValue:
    try:
        return cast(JsonValue, json.loads(raw))
    except json.JSONDecodeError as exc:
        raise VendorOutputError(f"{label} is not valid JSON") from exc


def _json_object(raw: str, *, label: str) -> JsonObject:
    try:
        return _JSON_OBJECT.validate_python(_decode_json(raw, label=label))
    except ValidationError as exc:
        raise VendorOutputError(f"{label} must be one JSON object") from exc


def _read_bounded_utf8(path: Path, *, label: str) -> str:
    try:
        with path.open("rb") as stream:
            payload = stream.read(_MAX_FINAL_RESPONSE_BYTES + 1)
    except OSError as exc:
        raise VendorOutputError(f"{label} is unavailable") from exc
    if len(payload) > _MAX_FINAL_RESPONSE_BYTES:
        raise VendorOutputError(f"{label} exceeds the runtime output limit")
    try:
        return payload.decode("utf-8")
    except UnicodeError as exc:
        raise VendorOutputError(f"{label} is not UTF-8") from exc


def _metadata(**values: JsonValue | None) -> JsonObject:
    return {key: value for key, value in values.items() if value is not None}


def _option(argv: list[str], flag: str, value: str | None) -> None:
    if value is not None:
        argv.extend((flag, value))


def _codex_native_schema_supported(value: JsonValue) -> bool:
    if isinstance(value, list):
        return all(_codex_native_schema_supported(item) for item in value)
    if not isinstance(value, dict):
        return True
    schema_type = value.get("type")
    object_schema = (
        schema_type == "object"
        or (isinstance(schema_type, list) and "object" in schema_type)
        or "properties" in value
    )
    if object_schema:
        properties = value.get("properties", {})
        required = value.get("required", [])
        if (
            value.get("additionalProperties") is not False
            or not isinstance(properties, dict)
            or not isinstance(required, list)
            or set(required) != set(properties)
        ):
            return False
    return all(_codex_native_schema_supported(item) for item in value.values())


class ClaudeAdapter:
    name: VendorName = "claude"
    executable_names = ("claude",)
    capabilities = _BASE_CAPABILITIES | {"model-override"}
    session_persistence: Literal["disabled"] = "disabled"

    def help_probes(
        self,
        executable: str,
        config: CliExecutorConfig,
    ) -> tuple[VendorHelpProbe, ...]:
        required = {
            "--json-schema",
            "--no-session-persistence",
            "--output-format",
            "--print",
            "--safe-mode",
            "--tools",
        }
        if config.model_override is not None:
            required.add("--model")
        return (
            VendorHelpProbe(
                argv=(executable, "--help"),
                required_flags=frozenset(required),
            ),
        )

    def auth_argv(self, executable: str) -> tuple[str, ...]:
        return executable, "auth", "status", "--json"

    def auth_succeeded(self, result: ProcessResult) -> bool:
        if result.exit_code != 0:
            return False
        try:
            payload = _json_object(result.stdout, label="Claude auth response")
        except VendorOutputError:
            return False
        return payload.get("loggedIn") is True

    def build_invocation(
        self,
        executable: str,
        config: CliExecutorConfig,
        *,
        prompt: str,
        workspace: Path,
        prompt_path: Path,
        schema_path: Path,
        output_path: Path,
    ) -> VendorInvocation:
        del workspace, prompt_path, output_path
        schema_json = json.dumps(
            json.loads(schema_path.read_text(encoding="utf-8")),
            separators=(",", ":"),
        )
        native_schema = len(schema_json.encode()) <= _MAX_INLINE_SCHEMA_BYTES
        argv = [
            executable,
            "--safe-mode",
            "--print",
            "--no-session-persistence",
            "--output-format",
            "json",
            "--tools",
            "",
        ]
        if native_schema:
            argv.extend(("--json-schema", schema_json))
        _option(argv, "--model", config.model_override)
        return VendorInvocation(
            argv=tuple(argv),
            stdin=prompt,
            schema_enforcement=(
                "vendor-native+runtime" if native_schema else "runtime"
            ),
        )

    def parse_output(
        self,
        result: ProcessResult,
        *,
        output_path: Path,
    ) -> ParsedVendorOutput:
        del output_path
        envelope = _json_object(result.stdout, label="Claude response")
        structured = envelope.get("structured_output")
        if structured is None:
            raw_result = envelope.get("result")
            if not isinstance(raw_result, str):
                raise VendorOutputError(
                    "Claude response has no structured_output or text result"
                )
            structured = _decode_json(raw_result, label="Claude final response")
        try:
            output = _JSON_OBJECT.validate_python(structured)
        except ValidationError as exc:
            raise VendorOutputError("Claude response has no structured_output object") from exc
        return ParsedVendorOutput(
            output=output,
            metadata=_metadata(session_id=envelope.get("session_id")),
        )


class CodexAdapter:
    name: VendorName = "codex"
    executable_names = ("codex",)
    capabilities = _BASE_CAPABILITIES | {"model-override"}
    session_persistence: Literal["disabled"] = "disabled"

    def help_probes(
        self,
        executable: str,
        config: CliExecutorConfig,
    ) -> tuple[VendorHelpProbe, ...]:
        required = {
            "--cd",
            "--color",
            "--config",
            "--disable",
            "--ephemeral",
            "--ignore-rules",
            "--ignore-user-config",
            "--json",
            "--output-last-message",
            "--output-schema",
            "--sandbox",
            "--skip-git-repo-check",
            "--strict-config",
        }
        if config.model_override is not None:
            required.add("--model")
        return (
            VendorHelpProbe(
                argv=(executable, "exec", "--help"),
                required_flags=frozenset(required),
            ),
        )

    def auth_argv(self, executable: str) -> tuple[str, ...]:
        return executable, "login", "status"

    def auth_succeeded(self, result: ProcessResult) -> bool:
        return result.exit_code == 0

    def build_invocation(
        self,
        executable: str,
        config: CliExecutorConfig,
        *,
        prompt: str,
        workspace: Path,
        prompt_path: Path,
        schema_path: Path,
        output_path: Path,
    ) -> VendorInvocation:
        del prompt_path
        schema = _decode_json(
            schema_path.read_text(encoding="utf-8"),
            label="Codex output schema",
        )
        native_schema = _codex_native_schema_supported(schema)
        argv = [
            executable,
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--ignore-rules",
            "--skip-git-repo-check",
            "--strict-config",
            "--config",
            "project_doc_max_bytes=0",
            "--disable",
            "multi_agent",
            "--disable",
            "multi_agent_v2",
            "--sandbox",
            "read-only",
            "--output-last-message",
            str(output_path),
            "--json",
            "--color",
            "never",
            "--cd",
            str(workspace),
        ]
        if native_schema:
            argv.extend(("--output-schema", str(schema_path)))
        _option(argv, "--model", config.model_override)
        argv.append("-")
        return VendorInvocation(
            argv=tuple(argv),
            stdin=prompt,
            schema_enforcement=(
                "vendor-native+runtime" if native_schema else "runtime"
            ),
        )

    def parse_output(
        self,
        result: ProcessResult,
        *,
        output_path: Path,
    ) -> ParsedVendorOutput:
        raw_output = _read_bounded_utf8(
            output_path,
            label="Codex final response file",
        )
        session_id: JsonValue | None = None
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            event = _json_object(line, label="Codex JSONL event")
            if event.get("type") == "thread.started" and isinstance(
                event.get("thread_id"), str
            ):
                session_id = event["thread_id"]
        return ParsedVendorOutput(
            output=_json_object(raw_output, label="Codex final response"),
            metadata=_metadata(session_id=session_id),
        )


class CopilotAdapter:
    name: VendorName = "copilot"
    executable_names = ("copilot",)
    capabilities = _BASE_CAPABILITIES | {"agent-profile", "model-override"}
    session_persistence: Literal["vendor-default"] = "vendor-default"

    def help_probes(
        self,
        executable: str,
        config: CliExecutorConfig,
    ) -> tuple[VendorHelpProbe, ...]:
        required = {
            "--attachment",
            "--disable-builtin-mcps",
            "--no-ask-user",
            "--no-auto-update",
            "--no-bash-env",
            "--no-color",
            "--no-custom-instructions",
            "--no-experimental",
            "--no-remote",
            "--no-remote-export",
            "--output-format",
            "--prompt",
            "--silent",
            "--stream",
            "-C",
        }
        if config.agent_profile is not None:
            required.add("--agent")
        if config.model_override is not None:
            required.add("--model")
        return (
            VendorHelpProbe(
                argv=(executable, "--help"),
                required_flags=frozenset(required),
            ),
        )

    def auth_argv(self, executable: str) -> None:
        del executable
        return None

    def auth_succeeded(self, result: ProcessResult) -> bool:
        del result
        return True

    def build_invocation(
        self,
        executable: str,
        config: CliExecutorConfig,
        *,
        prompt: str,
        workspace: Path,
        prompt_path: Path,
        schema_path: Path,
        output_path: Path,
    ) -> VendorInvocation:
        del prompt, schema_path, output_path
        argv = [
            executable,
            "--prompt",
            "Execute the complete graph-skill AgentTask in the attached UTF-8 "
            "file and return only the requested JSON object.",
            "--attachment",
            str(prompt_path),
            "--silent",
            "--stream=off",
            "--output-format=text",
            "--no-ask-user",
            "--no-custom-instructions",
            "--no-auto-update",
            "--no-bash-env",
            "--no-experimental",
            "--no-remote",
            "--no-remote-export",
            "--no-color",
            "--disable-builtin-mcps",
            "-C",
            str(workspace),
        ]
        _option(argv, "--agent", config.agent_profile)
        _option(argv, "--model", config.model_override)
        return VendorInvocation(
            argv=tuple(argv),
            stdin=None,
            schema_enforcement="runtime",
        )

    def parse_output(
        self,
        result: ProcessResult,
        *,
        output_path: Path,
    ) -> ParsedVendorOutput:
        del output_path
        return ParsedVendorOutput(
            output=_json_object(result.stdout, label="Copilot final response"),
            metadata={},
        )


class CursorAdapter:
    name: VendorName = "cursor"
    executable_names = ("cursor-agent",)
    capabilities = _BASE_CAPABILITIES | {"model-override"}
    session_persistence: Literal["vendor-default"] = "vendor-default"

    def help_probes(
        self,
        executable: str,
        config: CliExecutorConfig,
    ) -> tuple[VendorHelpProbe, ...]:
        required = {"--output-format", "--print"}
        if config.model_override is not None:
            required.add("--model")
        return (
            VendorHelpProbe(
                argv=(executable, "--help"),
                required_flags=frozenset(required),
            ),
        )

    def auth_argv(self, executable: str) -> tuple[str, ...]:
        return executable, "status"

    def auth_succeeded(self, result: ProcessResult) -> bool:
        return result.exit_code == 0

    def build_invocation(
        self,
        executable: str,
        config: CliExecutorConfig,
        *,
        prompt: str,
        workspace: Path,
        prompt_path: Path,
        schema_path: Path,
        output_path: Path,
    ) -> VendorInvocation:
        del workspace, prompt_path, schema_path, output_path
        argv = [executable, "--print", "--output-format", "json"]
        _option(argv, "--model", config.model_override)
        return VendorInvocation(
            argv=tuple(argv),
            stdin=prompt,
            schema_enforcement="runtime",
        )

    def parse_output(
        self,
        result: ProcessResult,
        *,
        output_path: Path,
    ) -> ParsedVendorOutput:
        del output_path
        envelope = _json_object(result.stdout, label="Cursor response")
        if envelope.get("type") != "result" or envelope.get("is_error") is not False:
            raise VendorOutputError("Cursor response is not a successful result")
        raw_result = envelope.get("result")
        if not isinstance(raw_result, str):
            raise VendorOutputError("Cursor response has no text result")
        return ParsedVendorOutput(
            output=_json_object(raw_result, label="Cursor final response"),
            metadata=_metadata(session_id=envelope.get("session_id")),
        )


class GeminiAdapter:
    name: VendorName = "gemini"
    executable_names = ("gemini",)
    capabilities = _BASE_CAPABILITIES | {"agent-profile", "model-override"}
    session_persistence: Literal["vendor-default"] = "vendor-default"

    def help_probes(
        self,
        executable: str,
        config: CliExecutorConfig,
    ) -> tuple[VendorHelpProbe, ...]:
        required = {
            "--extensions",
            "--output-format",
            "--prompt",
            "--sandbox",
            "--skip-trust",
        }
        if config.model_override is not None:
            required.add("--model")
        return (
            VendorHelpProbe(
                argv=(executable, "--help"),
                required_flags=frozenset(required),
            ),
        )

    def auth_argv(self, executable: str) -> None:
        del executable
        return None

    def auth_succeeded(self, result: ProcessResult) -> bool:
        del result
        return True

    def build_invocation(
        self,
        executable: str,
        config: CliExecutorConfig,
        *,
        prompt: str,
        workspace: Path,
        prompt_path: Path,
        schema_path: Path,
        output_path: Path,
    ) -> VendorInvocation:
        del workspace, prompt_path, schema_path, output_path
        argv = [
            executable,
            "--output-format",
            "json",
            "--sandbox",
            "--skip-trust",
            "--extensions",
            "none",
            "--prompt",
            "Execute the graph-skill task supplied on stdin and return only its JSON output.",
        ]
        _option(argv, "--model", config.model_override)
        if config.agent_profile is not None:
            prompt = f"@{config.agent_profile}\n\n{prompt}"
        return VendorInvocation(
            argv=tuple(argv),
            stdin=prompt,
            schema_enforcement="runtime",
        )

    def parse_output(
        self,
        result: ProcessResult,
        *,
        output_path: Path,
    ) -> ParsedVendorOutput:
        del output_path
        envelope = _json_object(result.stdout, label="Gemini response")
        if envelope.get("error") is not None:
            raise VendorOutputError("Gemini response contains an error")
        response = envelope.get("response")
        if not isinstance(response, str):
            raise VendorOutputError("Gemini response has no text response")
        return ParsedVendorOutput(
            output=_json_object(response, label="Gemini final response"),
            metadata={},
        )


class OpenCodeAdapter:
    name: VendorName = "opencode"
    executable_names = ("opencode",)
    capabilities = _BASE_CAPABILITIES | {"agent-profile", "model-override"}
    session_persistence: Literal["vendor-default"] = "vendor-default"

    def help_probes(
        self,
        executable: str,
        config: CliExecutorConfig,
    ) -> tuple[VendorHelpProbe, ...]:
        required = {"--dir", "--format"}
        if config.agent_profile is not None:
            required.add("--agent")
        if config.model_override is not None:
            required.add("--model")
        return (
            VendorHelpProbe(
                argv=(executable, "--help"),
                required_flags=frozenset({"--pure"}),
            ),
            VendorHelpProbe(
                argv=(executable, "run", "--help"),
                required_flags=frozenset(required | {"--file"}),
            ),
        )

    def auth_argv(self, executable: str) -> None:
        del executable
        return None

    def auth_succeeded(self, result: ProcessResult) -> bool:
        del result
        return True

    def build_invocation(
        self,
        executable: str,
        config: CliExecutorConfig,
        *,
        prompt: str,
        workspace: Path,
        prompt_path: Path,
        schema_path: Path,
        output_path: Path,
    ) -> VendorInvocation:
        del prompt, schema_path, output_path
        argv = [
            executable,
            "--pure",
            "run",
            "--format",
            "json",
            "--dir",
            str(workspace),
            "--file",
            str(prompt_path),
        ]
        _option(argv, "--agent", config.agent_profile)
        _option(argv, "--model", config.model_override)
        argv.append(
            "Execute the complete graph-skill AgentTask in the attached UTF-8 "
            "file and return only the requested JSON object."
        )
        return VendorInvocation(
            argv=tuple(argv),
            stdin=None,
            schema_enforcement="runtime",
        )

    def parse_output(
        self,
        result: ProcessResult,
        *,
        output_path: Path,
    ) -> ParsedVendorOutput:
        del output_path
        chunks: list[str] = []
        session_id: JsonValue | None = None
        saw_finish = False
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            event = _json_object(line, label="OpenCode JSON event")
            if session_id is None and isinstance(event.get("sessionID"), str):
                session_id = event["sessionID"]
            event_type = event.get("type")
            part = event.get("part")
            if event_type == "text" and isinstance(part, dict):
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)
            elif event_type == "step_finish":
                saw_finish = True
        if not saw_finish:
            raise VendorOutputError("OpenCode response has no step_finish event")
        if not chunks:
            raise VendorOutputError("OpenCode response has no text event")
        return ParsedVendorOutput(
            output=_json_object("".join(chunks), label="OpenCode final response"),
            metadata=_metadata(session_id=session_id),
        )


_ADAPTERS: dict[VendorName, VendorAdapter] = {
    "claude": ClaudeAdapter(),
    "codex": CodexAdapter(),
    "copilot": CopilotAdapter(),
    "cursor": CursorAdapter(),
    "gemini": GeminiAdapter(),
    "opencode": OpenCodeAdapter(),
}


def vendor_adapter(vendor: VendorName) -> VendorAdapter:
    return _ADAPTERS[vendor]
