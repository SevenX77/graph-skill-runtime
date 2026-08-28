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
| Vendor process-tree ownership | [`SubprocessProcessRunner`](../src/graph_skill_runtime/adapters/process.py) uses a Win32 Job Object on Windows and a new process group on POSIX; a denied POSIX group signal falls back only to bounded exact-PGID/effective-UID member signaling |
| Platform CI configuration | [CI](../.github/workflows/ci.yml) builds one candidate on Ubuntu with Python 3.11, runs source tests on Ubuntu Python 3.11/3.12/3.13, and accepts that same candidate on Ubuntu, Windows, and macOS with Python 3.11 |
| Release-artifact binding | [`accept_release_artifacts.py`](../scripts/accept_release_artifacts.py) records one exact source commit plus wheel/sdist filename, size, and SHA-256 in `gskill.release-artifacts.v1`; its acceptance evidence records the consumed manifest SHA-256 |

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

On POSIX, `subprocess.Popen(..., start_new_session=True)` creates a new session whose process group id is the child PID. Timeout, cancellation, and successful-parent cleanup first use group-wide signaling: `SIGTERM`, a fixed one-second grace period, then `SIGKILL` for remaining members. This borrows the mature session/process-group mechanism exposed by [Python's subprocess API](https://docs.python.org/3/library/subprocess.html#popen-constructor) and [`os.killpg`](https://docs.python.org/3/library/os.html#os.killpg). It does not use shell job control, a daemon, or detached PID discovery.

Hosted Darwin demonstrated a narrower failure mode: group-wide `killpg` may return `EPERM` when the group contains a process the caller is not permitted to signal. That behavior follows Apple's documented [`killpg(2)` permission semantics](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/killpg.2.html). A denied group operation therefore does not prove that the runtime-owned members are unsignalable.

On `PermissionError` only, the adapter checks `/bin/ps` and then `/usr/bin/ps`, runs the first available executable with `-axo pid=,pgid=,uid=`, and bounds that inspection to two seconds and 1 MiB of output. It accepts only well-formed integer rows whose PGID exactly equals the attempt's process-group id and whose UID equals the runtime's effective UID; it excludes the runtime process itself, deduplicates the PIDs, and signals those members individually. A missing `ps`, nonzero result, oversized output, malformed row, or invalid UTF-8 fails inspection rather than broadening the target. The same narrow fallback applies to the grace-period `SIGKILL` pass. It is not recursive process discovery and never targets a different PGID or UID.

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

## Immutable release-candidate boundary

Phase 6 accepts one built candidate through [`scripts/accept_release_artifacts.py`](../scripts/accept_release_artifacts.py). The boundary has two public repository commands and one internal worker:

- `validate` requires the distribution directory to contain exactly one wheel and one `.tar.gz` source distribution. It validates distribution/version/`Requires-Python` metadata, the `gskill` entry point, the wheel's `py3-none-any` pure-Python declaration, and portable archive names. It rejects wheel symlinks; each source-distribution member must be a regular file or directory. The wheel rejects `graph_agent/` and `graph_skill_runtime/examples/`; the sdist rejects `src/graph_agent/` and `src/graph_skill_runtime/examples/`. Both treat the MoirAI asset subtree as the exact closed inventory derived from packaged `integration.json`. The sdist may contain repository-level examples and tests as source corpus; it does not install them as package content. The validator does not freeze every ordinary runtime source member into one full-archive whitelist. It writes `gskill.release-artifacts.v1` with the supplied exact source commit and the two artifacts' filenames, positive sizes, and SHA-256 values.
- `accept` loads that manifest, requires each artifact's current size and SHA-256 to match its manifest entry, revalidates both archives, and requires `--expected-source-commit` to equal the manifest's source commit. It copies only those verified bytes into a temporary immutable-candidate directory, installs pip-wheel, uv-wheel, and pip-sdist channels in separate controlled environments, and writes `gskill.package-acceptance.v1`. The evidence records the SHA-256 of the manifest it consumed. The command has no external expected-manifest-hash input; equal `artifact_manifest_sha256` values across platform evidence prove that those runs consumed the same manifest.
- `installed-smoke` is the internal per-channel worker. The isolated environment's Python executes the worker, and `graph_skill_runtime` must resolve inside that environment rather than the checkout. It rejects provider extras, installed `graph_skill_runtime/examples/`, and installed `graph.yaml`; checks distribution/version/console identity and the six-target read-only host detector; opens a real stdio MCP session, enumerates exactly the eight public runtime tools, and successfully invokes MCP `compile`. It exercises the installed CLI's compile/inspect/predict/run behavior with spaces and non-ASCII text, and the installed MoirAI CLI's Claude/Codex project lifecycle `planned → installed → unchanged → uninstalled`.

The installed handoff smoke uses the deterministic host-native protocol rather than a vendor executable. It observes `run → reopened agent_required → submit completed → exact duplicate completed → reopened terminal completed`, checks both SQLite databases with `PRAGMA integrity_check`, renames and reopens them after closing connections, and requires the immutable request snapshot and trace. On Windows, successful database rename also proves that the acceptance process released incompatible file handles. Controlled HOME/config/cache snapshots must show no unexpected host-state mutation; only the runtime-owned compile cache is permitted.

The release topology borrows three mature packaging choices:

- The [PyPA GitHub Actions publishing guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/) separates build from publish and hands an immutable artifact between jobs. This repository likewise builds once, validates and uploads that candidate, and makes every platform and the publisher download it; it does not rebuild independently before upload.
- [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/) binds publication to a named GitHub environment and short-lived OpenID Connect identity. The publish job therefore uses environment `pypi` and the narrow `id-token: write` permission, with no long-lived package token in workflow configuration.
- The [uv package guide](https://docs.astral.sh/uv/guides/package/) defines `uv build --no-sources` as the check that a package builds without local source overrides. Both CI and release use it so a workspace-only `tool.uv.sources` path cannot make an otherwise unpublishable candidate appear valid.

These choices prove provenance and pre-publication behavior, not registry state. A later release must still use the exact accepted bytes. Creating a tag, publishing a GitHub Release, configuring the PyPI project/trusted publisher, and observing the registry upload are external actions; none has occurred for `0.1.0a1`.

## CI and verification evidence

The configured CI topology is:

- `quality-gates` on Ubuntu/Python 3.11 runs Ruff, strict mypy, contract-manifest validation, and dependency audit. It builds once with `uv build --no-sources`, validates the wheel/source-distribution pair, and uploads those distributions with their artifact manifest.
- `runtime-tests` runs the complete pytest suite, including distribution-contract tests, on Ubuntu/Python 3.11, 3.12, and 3.13. The Python 3.11 job also downloads and accepts the candidate built by `quality-gates`.
- `cross-platform-smoke` runs Ruff, strict mypy, contract-manifest validation, and the complete pytest suite, then accepts that same candidate on Windows/Python 3.11 and macOS/Python 3.11.

The repository's exact required checks are `quality-gates`, `runtime-tests (3.11)`, `runtime-tests (3.12)`, `runtime-tests (3.13)`, `cross-platform-smoke (windows-latest)`, and `cross-platform-smoke (macos-latest)`. The latter five jobs declare `needs: quality-gates`; reusing these existing required-check names places same-candidate artifact acceptance on the merge-gating path rather than creating an advisory side job.

A configuration entry or successful Linux run does not prove Windows or macOS behavior. A change to paths, encodings, subprocesses, atomic writes, locks, SQLite storage, or cleanup must have an OS-independent unit test where possible and a real affected-platform run where platform semantics matter. Record the command, operating system, Python version, and observed result before claiming support.

The current Phase 4 real-machine record is Microsoft Windows `10.0.26200` x64 with Python `3.11.15`. Codex CLI `0.144.1` completed a real `gskill run`; its trace progressed `agent_required` → `agent_dispatched` → `agent_started` → `agent_completed`, and the last three events shared one attempt id. Claude Code `2.1.222` passed executable, version, and required-flag probes on the same host but its exposed authentication probe failed, so the runtime returned structured `GSKILL_EXECUTOR_UNAVAILABLE` before creating the handoff database. A deliberately missing Copilot executable likewise returned `executable-not-found` before handoff creation. Copilot, Cursor, Gemini, and OpenCode were not installed, Claude was not authenticated, and no macOS or Linux direct-vendor run was performed.

Remote source-checkout evidence now exists on the same implementation commit [`8928d13`](https://github.com/SevenX77/graph-skill-runtime/commit/8928d13b32c800a2ad303d02e1bd96551f969ab5). [Workflow run 33140732333](https://github.com/SevenX77/graph-skill-runtime/actions/runs/33140732333) passed `quality-gates`, `runtime-tests` for Python 3.11/3.12/3.13, `cross-platform-smoke (windows-latest)`, and `cross-platform-smoke (macos-latest)`. The CodeQL check also passed, including `Analyze Python`. The real macOS process test starts a descendant that ignores `SIGTERM` and verifies that the subsequent `SIGKILL` cleanup prevents it from surviving.

Fake-process adapter tests prove command construction, parsing, limits, lifecycle mapping, and failure behavior independent of an installed vendor. The Phase 4 remote Windows/macOS jobs prove the tested source-checkout process semantics on those runners, including the Darwin permission fallback; CodeQL proves only that its configured analysis completed successfully. Dynamic executable/version/help/auth probes decide whether one local attempt can proceed; they are not a release-wide promise for every CLI version or operating system.

### Phase 6 acceptance evidence — 2026-08-28

Local validation on implementation commit `f7d5340d0c822f62786046724473b9005c41f1b1` passed Ruff, strict mypy over 149 source files, the contract-manifest validator, `1716 passed, 1 skipped`, seven distribution-contract tests, and `pip-audit` with no known vulnerabilities among resolved distributions. The audit skipped the unpublished local project; it is neither a source-code security audit nor publication evidence. On Python `3.11.15` / Windows 10 AMD64, one exact local candidate passed pip-wheel, uv-wheel, and pip-sdist acceptance. Documentation changes alter distribution bytes, so that local candidate's hashes are evidence for that run rather than fixed version constants.

[PR #9](https://github.com/SevenX77/graph-skill-runtime/pull/9) had head `f7d5340d`; [Actions run 33159834800](https://github.com/SevenX77/graph-skill-runtime/actions/runs/33159834800) checked out synthetic merge `67703295956350f6453dae24f4f0de50f8d448d9`. The latter, not the PR head, is the `source_commit` recorded by all three platform acceptance reports. The run completed `quality-gates` in 39 seconds, runtime tests in 4m08s / 2m35s / 2m17s for Python 3.11 / 3.12 / 3.13, Windows smoke in 5m04s, and macOS smoke in 3m44s. CodeQL `Analyze Python` also succeeded in 1m17s; it remains analysis evidence, not artifact acceptance.

The platform reports bind the candidate as follows:

| Evidence field | Value on Ubuntu, Windows, and macOS |
| --- | --- |
| Distribution/version | `graph-skill-runtime` / `0.1.0a1` |
| Source commit | `67703295956350f6453dae24f4f0de50f8d448d9` |
| Artifact-manifest SHA-256 | `36769e48c89a3396ee38fea72aa0d2c3f0ae3aad98dab242bcc2f719ac6993ca` |
| Wheel | SHA-256 `fc9e3508ba134cb82593d1175777ad8d237622effad9e5d1ceac9a528614888b`; 477655 bytes |
| Source distribution | SHA-256 `674cea440f513e17d8856dcbbe0129981dfd55cc305a593e62a1ba2f3c76f75d`; 1451852 bytes |

The equal manifest digest proves that the three reports consumed the same manifest; the recorded artifact size and SHA-256 values bind that manifest to the wheel and source distribution. `accept` itself has no separate expected-manifest-hash parameter. These values identify this first accepted remote candidate and do not permanently define every `0.1.0a1` build.

| Acceptance environment | Installed channels | Shared observable result |
| --- | --- | --- |
| Linux x86_64, Python 3.11.16 | pip-wheel, uv-wheel, pip-sdist | compile passed; predict/run completed; handoff statuses `[agent_required, agent_required, completed, completed, completed]`; integration statuses `[planned, installed, unchanged, uninstalled]`; unexpected host-state changes `[]` |
| Windows 10 AMD64, Python 3.11.16 | pip-wheel, uv-wheel, pip-sdist | same |
| Darwin arm64, Python 3.11.16 | pip-wheel, uv-wheel, pip-sdist | same |

These observations satisfy Phase 6's defined cross-platform package/release-candidate exit criteria. They do not execute real vendor CLIs: the installed handoff uses deterministic host-native result submission, so the direct-vendor support statement remains the Windows/Codex record above. They also do not prove publication. As observed on 2026-08-28, the repository release list was empty and the `graph-skill-runtime` JSON endpoints on both PyPI and TestPyPI returned 404; no tag release, GitHub Release, registry upload, PyPI project, or trusted-publisher relationship had been created or exercised.

Run the local baseline gates from the repository root:

```bash
uv run ruff check src tests scripts tools
uv run mypy --strict src
uv run pytest --tb=short -q
uv run python scripts/validate_round28_manifest.py spec/features.yaml spec/source_file_map.yaml spec/contract_map.yaml
uv build --no-sources
uv run pip-audit
```

Use the exact `validate` and `accept` command forms in the [repository guide](../README.md#phase-6-package-acceptance-and-publication-boundary) when establishing acceptance for a release candidate.

## Review checklist

Before merging a cross-platform-sensitive change, verify that:

- every text boundary names its encoding, and authored versus runtime-owned input uses the correct reader;
- repository files remain UTF-8 with LF and no case-only path pair was introduced;
- paths are resolved at a named boundary and cannot escape an allowed root;
- subprocess argv, environment, working directory, decoding, timeout, cancellation, and failure mapping are explicit;
- Windows starts the stdin-blocked supervisor, assigns its Job Object before releasing vendor argv, fails closed on assignment failure, and documents the supervisor PID semantics;
- POSIX uses one owned session/process group and cleans it after success as well as timeout or cancellation;
- a POSIX `killpg` permission fallback is bounded, selects exact-PGID/effective-UID members only, and fails rather than widening its target when inspection is unavailable or malformed;
- resource materialization and process-tree ownership are not described as a cross-vendor hard sandbox;
- replacement or locking behavior has one owner and the same observable contract on Windows and POSIX;
- tests prove the resulting state or failure, not merely that a function or command returned;
- actual platform results are distinguished from configured but unrun CI;
- every platform acceptance report names the expected source commit and records the same consumed-manifest digest before results are combined;
- acceptance, release creation, and registry publication are reported as separate states.
