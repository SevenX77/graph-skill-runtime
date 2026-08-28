"""Cross-platform, shell-free process-tree runner."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO, cast

from graph_skill_runtime.adapters.windows_job import WindowsJob
from graph_skill_runtime.ports.process import (
    CancellationProbe,
    ProcessCancelledError,
    ProcessOutputLimitError,
    ProcessRequest,
    ProcessResult,
    ProcessRunner,
    ProcessStarted,
    ProcessTimedOutError,
)

_POLL_SECONDS = 0.1
_TERMINATE_GRACE_SECONDS = 1.0
_POSIX_SIGKILL = int(getattr(signal, "SIGKILL", 9))

_WINDOWS_SUPERVISOR = """
import json
import subprocess
import sys

request = json.load(sys.stdin)
argv = request["argv"]
stdin = request["stdin"]
if stdin is None:
    completed = subprocess.run(argv, stdin=subprocess.DEVNULL, shell=False)
else:
    completed = subprocess.run(
        argv,
        input=stdin,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
raise SystemExit(completed.returncode)
"""


@dataclass
class _SpawnedProcess:
    process: subprocess.Popen[str]
    input_payload: str | None
    windows_job: WindowsJob | None = None


def _read_output(stream: IO[bytes], max_output_bytes: int) -> str:
    stream.seek(0)
    payload = stream.read(max_output_bytes + 1)
    if len(payload) > max_output_bytes:
        raise ProcessOutputLimitError(max_output_bytes)
    return payload.decode("utf-8", errors="replace")


def _output_limit_exceeded(
    stdout_file: IO[bytes],
    stderr_file: IO[bytes],
    max_output_bytes: int,
) -> bool:
    return (
        os.fstat(stdout_file.fileno()).st_size
        + os.fstat(stderr_file.fileno()).st_size
        > max_output_bytes
    )


def _windows_taskkill(process_id: int) -> None:
    system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
    taskkill = system_root / "System32" / "taskkill.exe"
    if not taskkill.is_file():
        return
    creation_flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        subprocess.run(
            [str(taskkill), "/PID", str(process_id), "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=5.0,
            creationflags=creation_flags,
        )
    except (OSError, subprocess.SubprocessError):
        return


def _request_windows_tree_termination(spawned: _SpawnedProcess) -> None:
    process = spawned.process
    if spawned.windows_job is not None:
        try:
            spawned.windows_job.terminate()
            return
        except OSError:
            pass
    _windows_taskkill(process.pid)


def _signal_posix_process_group(process_id: int, requested_signal: int) -> bool:
    # Platform stubs intentionally omit killpg on Windows even though this module
    # is type-checked there; runtime dispatch guarantees this branch is POSIX-only.
    kill_process_group = cast(
        Callable[[int, int], None],
        os.__dict__["killpg"],
    )
    try:
        kill_process_group(process_id, requested_signal)
    except ProcessLookupError:
        return False
    return True


def _terminate_windows_tree(spawned: _SpawnedProcess) -> None:
    process = spawned.process
    _request_windows_tree_termination(spawned)
    if process.poll() is None:
        try:
            process.wait(timeout=_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
            except OSError:
                pass
    if process.poll() is None:
        try:
            process.wait(timeout=_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            pass


def _terminate_posix_tree(spawned: _SpawnedProcess) -> None:
    process = spawned.process
    group_existed = _signal_posix_process_group(process.pid, signal.SIGTERM)
    if group_existed:
        # A zero-signal group probe is not portable evidence: macOS can return
        # EPERM when group membership changes during termination. Give the
        # owned group a fixed grace interval, then enforce the deadline.
        time.sleep(_TERMINATE_GRACE_SECONDS)
        try:
            _signal_posix_process_group(process.pid, _POSIX_SIGKILL)
        except PermissionError:
            # macOS can retain a non-signalable group identity after every
            # owned member has exited. Never mask a still-live direct child.
            if process.poll() is None:
                process.kill()
    if process.poll() is None:
        try:
            process.wait(timeout=_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            pass


def _terminate_process_tree(spawned: _SpawnedProcess) -> None:
    if sys.platform == "win32":
        _terminate_windows_tree(spawned)
    else:
        _terminate_posix_tree(spawned)


def _validate_request(
    request: ProcessRequest,
    cancellation: CancellationProbe | None,
) -> None:
    if not request.argv or not request.argv[0]:
        raise ValueError("process argv must contain an executable")
    if not request.cwd.is_absolute() or not request.cwd.is_dir():
        raise ValueError("process cwd must be an existing absolute directory")
    if request.timeout_seconds <= 0:
        raise ValueError("process timeout must be positive")
    if request.max_output_bytes <= 0:
        raise ValueError("process output limit must be positive")
    if cancellation is not None and cancellation.is_cancelled():
        raise ProcessCancelledError("process cancelled before start")


def _spawn_process(
    request: ProcessRequest,
    stdout_file: IO[bytes],
    stderr_file: IO[bytes],
) -> _SpawnedProcess:
    creation_flags = 0
    start_new_session = sys.platform != "win32"
    argv = list(request.argv)
    input_payload = request.stdin
    windows_job: WindowsJob | None = None
    if sys.platform == "win32":
        creation_flags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        creation_flags |= int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        windows_job = WindowsJob.create()
        argv = [sys.executable, "-X", "utf8", "-c", _WINDOWS_SUPERVISOR]
        input_payload = json.dumps(
            {"argv": list(request.argv), "stdin": request.stdin},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE if input_payload is not None else subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            cwd=str(request.cwd),
            env=dict(request.environment),
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            start_new_session=start_new_session,
            creationflags=creation_flags,
        )
    except BaseException:
        if windows_job is not None:
            windows_job.close()
        raise
    if windows_job is not None:
        try:
            windows_job.assign(process.pid)
        except BaseException:
            process.kill()
            process.wait()
            windows_job.close()
            raise
    return _SpawnedProcess(
        process=process,
        input_payload=input_payload,
        windows_job=windows_job,
    )


def _communicate_until_done(
    spawned: _SpawnedProcess,
    request: ProcessRequest,
    stdout_file: IO[bytes],
    stderr_file: IO[bytes],
    *,
    started_at: float,
    cancellation: CancellationProbe | None,
) -> None:
    process = spawned.process
    pending_input = spawned.input_payload
    while True:
        if _output_limit_exceeded(
            stdout_file,
            stderr_file,
            request.max_output_bytes,
        ):
            raise ProcessOutputLimitError(request.max_output_bytes)
        if cancellation is not None and cancellation.is_cancelled():
            raise ProcessCancelledError("process cancelled")
        remaining = request.timeout_seconds - (time.monotonic() - started_at)
        if remaining <= 0:
            raise ProcessTimedOutError(request.timeout_seconds)
        try:
            process.communicate(
                input=pending_input,
                timeout=min(_POLL_SECONDS, remaining),
            )
            if _output_limit_exceeded(
                stdout_file,
                stderr_file,
                request.max_output_bytes,
            ):
                raise ProcessOutputLimitError(request.max_output_bytes)
            return
        except subprocess.TimeoutExpired:
            pending_input = None


def _wait_for_completion(
    spawned: _SpawnedProcess,
    request: ProcessRequest,
    stdout_file: IO[bytes],
    stderr_file: IO[bytes],
    *,
    started_at: float,
    cancellation: CancellationProbe | None,
) -> None:
    try:
        _communicate_until_done(
            spawned,
            request,
            stdout_file,
            stderr_file,
            started_at=started_at,
            cancellation=cancellation,
        )
    except KeyboardInterrupt:
        raise ProcessCancelledError("process cancelled by keyboard interrupt") from None


class SubprocessProcessRunner(ProcessRunner):
    """Run a direct child in a new process group and terminate its whole tree."""

    def run(
        self,
        request: ProcessRequest,
        *,
        cancellation: CancellationProbe | None = None,
        on_started: ProcessStarted | None = None,
    ) -> ProcessResult:
        _validate_request(request, cancellation)
        started_at = time.monotonic()
        with tempfile.TemporaryFile(mode="w+b") as stdout_file, tempfile.TemporaryFile(
            mode="w+b"
        ) as stderr_file:
            spawned = _spawn_process(request, stdout_file, stderr_file)
            process = spawned.process
            try:
                if on_started is not None:
                    on_started(process.pid)
                _wait_for_completion(
                    spawned,
                    request,
                    stdout_file,
                    stderr_file,
                    started_at=started_at,
                    cancellation=cancellation,
                )
            except BaseException:
                _terminate_process_tree(spawned)
                raise
            finally:
                if spawned.windows_job is not None:
                    spawned.windows_job.close()
                elif process.poll() is not None:
                    _terminate_process_tree(spawned)

            stdout = _read_output(stdout_file, request.max_output_bytes)
            stderr = _read_output(stderr_file, request.max_output_bytes)
            return ProcessResult(
                exit_code=int(process.returncode),
                stdout=stdout,
                stderr=stderr,
                duration_seconds=time.monotonic() - started_at,
                process_id=process.pid,
            )
