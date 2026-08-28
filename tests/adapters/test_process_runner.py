from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from graph_skill_runtime.adapters.process import SubprocessProcessRunner
from graph_skill_runtime.adapters.windows_job import WindowsJob
from graph_skill_runtime.ports.process import (
    ProcessCancelledError,
    ProcessOutputLimitError,
    ProcessRequest,
    ProcessTimedOutError,
)


def _request(
    tmp_path: Path,
    *argv: str,
    stdin: str | None = None,
    timeout_seconds: float = 5.0,
    max_output_bytes: int = 4 * 1024 * 1024,
) -> ProcessRequest:
    return ProcessRequest(
        argv=tuple(argv),
        cwd=tmp_path.resolve(),
        environment=dict(os.environ),
        stdin=stdin,
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
    )


def test_runner_uses_explicit_utf8_stdin_cwd_and_environment(tmp_path: Path) -> None:
    script = (
        "import os, pathlib, sys; "
        "print(pathlib.Path.cwd().name); "
        "print(os.environ['GSKILL_PROCESS_TEST']); "
        "print(sys.stdin.read())"
    )
    request = _request(tmp_path, sys.executable, "-c", script, stdin="你好")
    request = ProcessRequest(
        **{
            **request.__dict__,
            "environment": {**request.environment, "GSKILL_PROCESS_TEST": "环境"},
        }
    )

    result = SubprocessProcessRunner().run(request)

    assert result.exit_code == 0
    assert result.stdout.splitlines() == [tmp_path.name, "环境", "你好"]
    assert result.stderr == ""
    assert result.duration_seconds >= 0
    assert result.process_id > 0


def test_timeout_terminates_the_whole_process_tree(tmp_path: Path) -> None:
    ready = tmp_path / "child-ready"
    forbidden = tmp_path / "child-survived"
    child_script = (
        "import pathlib, sys, time; "
        "time.sleep(1.0); pathlib.Path(sys.argv[1]).write_text('survived', encoding='utf-8')"
    )
    parent_script = (
        "import pathlib, subprocess, sys, time; "
        "subprocess.Popen([sys.executable, '-c', sys.argv[3], sys.argv[2]]); "
        "pathlib.Path(sys.argv[1]).write_text('ready', encoding='utf-8'); time.sleep(10)"
    )
    request = _request(
        tmp_path,
        sys.executable,
        "-c",
        parent_script,
        str(ready),
        str(forbidden),
        child_script,
        timeout_seconds=0.4,
    )

    with pytest.raises(ProcessTimedOutError):
        SubprocessProcessRunner().run(request)

    assert ready.is_file(), "the child must have started before timeout"
    time.sleep(1.1)
    assert not forbidden.exists(), "a timed-out vendor CLI must not leave descendants running"


def test_successful_parent_exit_also_cleans_up_lingering_descendants(
    tmp_path: Path,
) -> None:
    forbidden = tmp_path / "detached-child-survived"
    child_script = (
        "import pathlib, sys, time; "
        "time.sleep(0.8); pathlib.Path(sys.argv[1]).write_text('survived', encoding='utf-8')"
    )
    parent_script = (
        "import subprocess, sys; "
        "subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1]])"
    )

    result = SubprocessProcessRunner().run(
        _request(
            tmp_path,
            sys.executable,
            "-c",
            parent_script,
            str(forbidden),
            child_script,
        )
    )

    assert result.exit_code == 0
    time.sleep(0.9)
    assert not forbidden.exists(), "one CLI attempt owns its entire process tree"


class _CancelAfterStart:
    def __init__(self) -> None:
        self.started = False

    def is_cancelled(self) -> bool:
        return self.started


def test_cancellation_terminates_a_started_process(tmp_path: Path) -> None:
    cancellation = _CancelAfterStart()
    request = _request(
        tmp_path,
        sys.executable,
        "-c",
        "import time; time.sleep(10)",
    )

    with pytest.raises(ProcessCancelledError):
        SubprocessProcessRunner().run(
            request,
            cancellation=cancellation,
            on_started=lambda _process_id: setattr(cancellation, "started", True),
        )


def test_output_is_bounded_without_decoding_partial_utf8(tmp_path: Path) -> None:
    request = _request(
        tmp_path,
        sys.executable,
        "-c",
        "print('x' * 100)",
        max_output_bytes=20,
    )

    with pytest.raises(ProcessOutputLimitError):
        SubprocessProcessRunner().run(request)


def test_output_limit_is_shared_by_stdout_and_stderr(tmp_path: Path) -> None:
    request = _request(
        tmp_path,
        sys.executable,
        "-c",
        "import sys; print('x' * 14); print('y' * 14, file=sys.stderr)",
        max_output_bytes=20,
    )

    with pytest.raises(ProcessOutputLimitError):
        SubprocessProcessRunner().run(request)


def test_runner_never_requests_shell_execution(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    observed: dict[str, object] = {}

    class _Job:
        def assign(self, process_id: int) -> None:
            assert process_id == 123

        def terminate(self) -> None:
            raise AssertionError("completed process must not be terminated")

        def close(self) -> None:
            observed["job_closed"] = True

    class _Process:
        pid = 123
        returncode = 0

        def communicate(self, *, input: str | None, timeout: float) -> tuple[None, None]:
            del input, timeout
            return None, None

        def poll(self) -> int:
            return 0

    def fake_popen(*args: object, **kwargs: object) -> _Process:
        observed["args"] = args
        observed["kwargs"] = kwargs
        return _Process()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(WindowsJob, "create", lambda: _Job())
    request = _request(tmp_path, sys.executable, "-c", "pass")

    SubprocessProcessRunner().run(request)

    assert observed["kwargs"]["shell"] is False  # type: ignore[index]
    assert observed["kwargs"]["cwd"] == str(tmp_path.resolve())  # type: ignore[index]
    if sys.platform == "win32":
        assert observed["job_closed"] is True
        assert observed["kwargs"]["start_new_session"] is False  # type: ignore[index]
    else:
        assert "job_closed" not in observed
        assert observed["kwargs"]["start_new_session"] is True  # type: ignore[index]
