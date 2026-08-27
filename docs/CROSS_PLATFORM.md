# Cross-Platform Policy

This document is the authoritative Windows, macOS, and Linux policy for the standalone Python runtime. It applies to `src/graph_agent`, repository scripts and tools, tests, package builds, and runtime-owned files. It does not define behavior for Studio, a web frontend, Rust, Tauri, or Gateway; those components are outside this repository.

## Platform contract

The current package requires Python 3.11 or newer. Supported behavior must have the same observable inputs, outputs, state transitions, timeouts, and typed failures on Windows, macOS, and Linux. A platform-specific implementation is allowed only at a named adapter boundary and only when all implementations preserve that shared contract.

Repository text and text exchanged by the runtime use UTF-8. Repository line endings are LF. File paths are represented with `pathlib.Path` at filesystem boundaries. Code must not rely on a host locale, default text encoding, case-insensitive lookup, POSIX-only process behavior, or Unix path separators.

## Current enforcement in this repository

| Control | Current repository fact |
| --- | --- |
| Git text normalization | [`.gitattributes`](../.gitattributes) pins Markdown, Python, TOML, YAML, JSON, and shell scripts to LF |
| Explicit Python encodings | [`pyproject.toml`](../pyproject.toml) enables Ruff `PLW1514`, which rejects text `open()` calls without an encoding in linted code |
| Human-authored input boundary | [`read_authored_text`](../src/graph_agent/core/authored_text.py) decodes external authored files with `utf-8-sig` |
| Python child-process default | Tests set `PYTHONUTF8=1` for child Python processes; CI sets it for jobs |
| Atomic cache publication | [`save_to_cache`](../src/graph_agent/core/cache.py) writes a unique sibling temporary file and publishes with `os.replace` |
| Platform CI configuration | [CI](../.github/workflows/ci.yml) defines Linux gates and tests, plus Python 3.12 smoke jobs on `windows-latest` and `macos-latest` |

These controls are configured in the checkout. Phase 0 has not yet supplied a remote workflow run, so the CI file is not evidence that a platform job has passed.

## Text and encoding boundaries

### Human-authored input

Skill Markdown, validator source, and declared runtime input can be written by editors that add a leading UTF-8 byte-order mark (BOM). Read such files through:

```python
from graph_agent.core.authored_text import read_authored_text

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

The current contract-manifest validator follows the explicit UTF-8 decoding pattern. New vendor or host process adapters must implement the same boundary in one adapter instead of scattering process calls through domain code.

Windows and POSIX process trees differ. Code that starts long-lived or child-spawning processes must define whether cancellation stops only the direct child or the owned process tree, then test that behavior on each supported platform. Do not call Unix-only signals or process-group APIs from shared code without an explicit platform adapter and equivalent Windows semantics.

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
- replacement or locking behavior has one owner and the same observable contract on Windows and POSIX;
- tests prove the resulting state or failure, not merely that a function or command returned;
- actual platform results are distinguished from configured but unrun CI.
