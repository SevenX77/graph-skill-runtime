# Cross-Platform Policy

This document is the authoritative Windows, macOS, and Linux policy for the standalone Python runtime. It applies to `src/graph_skill_runtime`, repository scripts and tools, tests, package builds, and runtime-owned files. It does not define behavior for Studio, a web frontend, Rust, Tauri, or Gateway; those components are outside this repository.

## Platform contract

The current package requires Python 3.11 or newer. Supported behavior must have the same observable inputs, outputs, state transitions, timeouts, and typed failures on Windows, macOS, and Linux. A platform-specific implementation is allowed only at a named adapter boundary and only when all implementations preserve that shared contract.

Repository text and text exchanged by the runtime use UTF-8. Repository line endings are LF. File paths are represented with `pathlib.Path` at filesystem boundaries. Code must not rely on a host locale, default text encoding, case-insensitive lookup, POSIX-only process behavior, or Unix path separators.

## Current enforcement in this repository

| Control | Current repository fact |
| --- | --- |
| Git text normalization | [`.gitattributes`](../.gitattributes) pins Markdown, Python, TOML, YAML, JSON, and shell scripts to LF |
| Explicit Python encodings | [`pyproject.toml`](../pyproject.toml) enables Ruff `PLW1514`, which rejects text `open()` calls without an encoding in linted code |
| Human-authored input boundary | [`read_authored_text`](../src/graph_skill_runtime/core/authored_text.py) decodes external authored files with `utf-8-sig` |
| Python child-process default | Tests set `PYTHONUTF8=1` for child Python processes; CI sets it for jobs |
| Atomic cache publication | [`save_to_cache`](../src/graph_skill_runtime/core/cache.py) writes a unique sibling temporary file and publishes with `os.replace` |
| Vendor process-tree ownership | [`SubprocessProcessRunner`](../src/graph_skill_runtime/adapters/process.py) uses a Win32 Job Object on Windows and a new process group on POSIX; timeout, cancellation, success, and parent cleanup own the complete attempt tree |
| Platform CI configuration | [CI](../.github/workflows/ci.yml) defines Linux gates and tests, plus Python 3.12 smoke jobs on `windows-latest` and `macos-latest` |

These controls are configured in the checkout. CI configuration is not evidence that a particular workflow, platform, vendor CLI, or version has passed; support statements require the recorded result of an affected-platform run.

## Text and encoding boundaries

### Human-authored input

Skill Markdown, validator source, and declared runtime input can be written by editors that add a leading UTF-8 byte-order mark (BOM). Read such files through:

```python
from graph_skill_runtime.core.authored_text import read_authored_text

text = read_authored_text(path)
```

The function uses Python's `utf-8-sig` codec. It removes one leading encoding signature when present and otherwise decodes exactly like UTF-8. It does not remove a `\ufeff` character elsewhere in legitimate content.

Do not repair BOM handling at individual parser call sites with `lstrip("\ufeff")` or similar cleanup. That creates multiple interpretations of the same file and can remove authored content. If a new class of human-authored file enters the runtime, route it through the existing boundary.

### Runtime-owned text

Files written by this runtime use UTF-8 without a BOM. Read runtime-owned caches, traces, manifests, reports, and metrics with explicit `encoding="utf-8"`. Write exact cross-platform text with explicit encoding and LF normalization; when Python's newline translation could affect the serialized contract, pass `newline="\n"` or serialize bytes deliberately.

Do not use a system default encoding for convenience. `PYTHONUTF8=1` is a process-level backstop, not a replacement for explicit call-site encoding. Binary formats must use binary I/O and must not be decoded through a text fallback.

## Subprocess boundaries

Every text subprocess call must define both sides of the encoding contract:

- pass an argument vector rather than a shell-composed command string;
- use `text=True`, `encoding="utf-8"`, and `errors="replace"` when stdout or stderr is text;
- give the child an explicit working directory, timeout or cancellation policy, and the minimum required environment;
- set `PYTHONUTF8=1` in the child environment when launching Python so the producer and consumer agree on UTF-8;
- preserve structured failures such as executable-not-found, timeout, cancellation, and nonzero exit instead of collapsing them into an empty result.

The current contract-manifest validator and direct vendor CLI process adapter follow the explicit UTF-8 decoding pattern. New vendor or host process adapters must implement the same boundary in one adapter instead of scattering process calls through domain code.

Windows and POSIX process trees differ. Code that starts long-lived or child-spawning processes must own and stop the complete process tree, then test that behavior on each supported platform. Do not call Unix-only signals or process-group APIs from shared code without an explicit platform adapter and equivalent Windows semantics.

## Direct CLI process-tree ownership

Each Phase 4 Agent attempt runs through the provider-neutral process Port in [`ports/process.py`](../src/graph_skill_runtime/ports/process.py). The request contains an argv tuple, existing absolute working directory, explicit environment, optional UTF-8 stdin, positive timeout, and combined output limit. The adapter always uses `shell=False`, captures stdout and stderr in bounded temporary files, polls cancellation and the monotonic deadline, decodes with UTF-8 replacement behavior, and removes its temporary task directory after the attempt. The complete business prompt travels by stdin for Claude, Codex, Cursor, and Gemini or by a UTF-8 attachment file for Copilot and OpenCode; it never enters argv.

On Windows, starting a vendor process directly and assigning it to a Job Object afterward creates a race: the vendor can spawn an unowned descendant before assignment. The runtime therefore starts a Python supervisor that blocks while reading its vendor request from stdin, creates a Job Object with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, immediately assigns the supervisor, and only then sends the vendor argv. The assigned supervisor becomes the process-tree root and launches the vendor with `shell=False`. `AgentStartedEvent.process_id` is this owned supervisor PID; consumers must not assume it is the vendor's direct PID. If Job Object creation, configuration, process opening, or `AssignProcessToJobObject` fails, startup fails closed and kills the supervisor. It does not degrade to “kill only the direct child.”

Timeout or cancellation calls `TerminateJobObject`; closing the Job handle after normal parent completion also terminates lingering descendants because `KILL_ON_JOB_CLOSE` is active. A bounded `taskkill /T /F` attempt exists only as cleanup after an unexpected Job termination failure, not as the ownership mechanism. This design borrows the operating-system ownership primitive and failure bias documented by [Microsoft Win32 Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects): `AssignProcessToJobObject` establishes membership, `TerminateJobObject` stops the group, and kill-on-close makes parent lifetime observable. It deliberately does not invent a PID-file protocol, because PID existence cannot prove process-tree membership or generation.

On POSIX, `subprocess.Popen(..., start_new_session=True)` creates a new session whose process group id is the child PID. Timeout, cancellation, and successful-parent cleanup signal the entire group: `SIGTERM`, a one-second grace period, then `SIGKILL` for remaining members. This borrows the mature process-group mechanism exposed by [Python's subprocess API](https://docs.python.org/3/library/subprocess.html#popen-constructor). It does not use shell job control, a daemon, or detached PID discovery.

These controls define process ownership and cleanup, not one uniform vendor security sandbox. The CLI adapter also uses a fresh temporary cwd, a minimal allowlisted environment, vendor-exposed customization switches, and a prompt that forbids extra filesystem, shell, network, MCP, skill, and subagent tools. Vendor-managed authentication and configuration can still apply, and individual CLI tool/sandbox behavior differs. `AgentTask.allowed_paths` authorizes the runtime to materialize declared resources; it does not prove that a vendor process can read only those paths. Do not describe this boundary as a blank configuration, hard sandbox, or universal filesystem isolation.

## Paths and filenames

- Use `pathlib.Path` for filesystem operations. Do not assemble filesystem paths with literal `/` or `\` separators.
- Resolve caller-provided roots at the boundary. Pass resolved roots inward rather than letting separate modules infer paths from the current working directory.
- Keep user-facing or persisted identifiers separate from native paths. Use POSIX-style relative strings only when the contract explicitly defines a portable identifier; convert them to `Path` before filesystem access.
- Reject path traversal and out-of-root targets after resolution, not by string-prefix comparison.
- Do not add two files or directories whose paths differ only by case. A tree that works only on a case-sensitive filesystem is not portable.
- Tests that need temporary files use pytest temporary directories or another isolated temporary root, not fixed machine-local paths.

## Atomic replacement on Windows and POSIX

Writing a destination in place can expose a truncated or partial file to concurrent readers. For a replaceable single-file snapshot, use this publication shape:

1. Create a uniquely named temporary sibling in the destination directory.
2. Write the complete payload with the required encoding and newline contract.
3. Publish it with `os.replace(temp, destination)`.
4. Clean up the temporary file if publication fails.

Keeping the temporary file beside the destination keeps replacement on one filesystem. Atomic visibility is not the same as durable commit; data that must survive power loss needs an explicitly designed flush and directory-sync policy rather than an undocumented assumption.

Windows can reject `os.replace` when another process holds the destination with incompatible sharing flags. Failure behavior depends on the state owner:

- A best-effort cache may log the failure, remove its temporary file, and continue without updating the cache. The current compile cache uses this policy, and [`test_cache_write_is_atomic.py`](../tests/core/test_cache_write_is_atomic.py) owns its observable behavior.
- A durable checkpoint, manifest, or user-requested output must report a structured failure and must not claim that the new state committed. Do not silently apply the cache policy to durable data.

Do not create a delete-then-rename gap to work around Windows. A destination being open is a normal concurrency case that the owning contract must handle explicitly.

## Lock semantics

The current runtime has no project-defined cross-process file-lock abstraction. Do not infer a portable lock contract from one operating system's primitive or from SQLite's internal locking.

Any new cross-process lock must define, before implementation:

- the exact resource and state owner the lock protects;
- process versus thread scope and whether acquisition is reentrant;
- blocking, nonblocking, or bounded-wait acquisition;
- one timeout clock, retry interval, and typed timeout result shared by all platforms;
- crash and stale-owner behavior, including what evidence permits recovery;
- release and cleanup behavior on success, exception, cancellation, and process termination.

Windows and POSIX implementations must have the same observable wait and failure semantics. Prefer a nonblocking platform primitive inside a runtime-owned deadline loop when native blocking calls have different retry limits. A lock-file path merely existing is not proof that its owner is alive, and deleting that path is not a safe lock-stealing protocol without verified owner identity and generation.

Atomic replacement and locking solve different problems. Replacement prevents readers from observing half a snapshot; a lock coordinates a larger read-modify-write transaction. Use only the mechanism required by the state contract, and test interleavings rather than treating either mechanism as a general concurrency cure.

## CI and verification evidence

The configured CI topology is:

- Ubuntu quality gates: Ruff, strict mypy, contract-manifest validation, dependency audit, and build;
- Ubuntu runtime tests on Python 3.11, 3.12, and 3.13;
- full pytest smoke runs on Windows and macOS with Python 3.12.

A configuration entry or successful Linux run does not prove Windows or macOS behavior. A change to paths, encodings, subprocesses, atomic writes, locks, SQLite storage, or cleanup must have an OS-independent unit test where possible and a real affected-platform run where platform semantics matter. Record the command, operating system, Python version, and observed result before claiming support.

The current Phase 4 real-machine record is Microsoft Windows `10.0.26200` x64 with Python `3.11.15`. Codex CLI `0.144.1` completed a real `gskill run`; its trace progressed `agent_required` → `agent_dispatched` → `agent_started` → `agent_completed`, and the last three events shared one attempt id. Claude Code `2.1.222` passed executable, version, and required-flag probes on the same host but its exposed authentication probe failed, so the runtime returned structured `GSKILL_EXECUTOR_UNAVAILABLE` before creating the handoff database. A deliberately missing Copilot executable likewise returned `executable-not-found` before handoff creation. Copilot, Cursor, Gemini, and OpenCode were not installed, Claude was not authenticated, and no macOS or Linux direct-vendor run was performed.

Fake-process adapter tests prove command construction, parsing, limits, lifecycle mapping, and failure behavior independent of an installed vendor. Process-runner tests on the Windows evidence host prove whole-tree cleanup after timeout and successful parent exit. Those tests do not turn an uninstalled vendor or untested operating system into a supported operational combination. Dynamic executable/version/help/auth probes decide whether one local attempt can proceed; they are not a release-wide promise for every CLI version or operating system. Cross-platform release acceptance remains Phase 6.

Run the local baseline gates from the repository root:

```bash
uv run ruff check src tests scripts tools
uv run mypy --strict src
uv run pytest --tb=short -q
uv run python scripts/validate_round28_manifest.py spec/features.yaml spec/source_file_map.yaml spec/contract_map.yaml
uv build
uv run pip-audit
```

## Review checklist

Before merging a cross-platform-sensitive change, verify that:

- every text boundary names its encoding, and authored versus runtime-owned input uses the correct reader;
- repository files remain UTF-8 with LF and no case-only path pair was introduced;
- paths are resolved at a named boundary and cannot escape an allowed root;
- subprocess argv, environment, working directory, decoding, timeout, cancellation, and failure mapping are explicit;
- Windows starts the stdin-blocked supervisor, assigns its Job Object before releasing vendor argv, fails closed on assignment failure, and documents the supervisor PID semantics;
- POSIX uses one owned session/process group and cleans it after success as well as timeout or cancellation;
- resource materialization and process-tree ownership are not described as a cross-vendor hard sandbox;
- replacement or locking behavior has one owner and the same observable contract on Windows and POSIX;
- tests prove the resulting state or failure, not merely that a function or command returned;
- actual platform results are distinguished from configured but unrun CI.
