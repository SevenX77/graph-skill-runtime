"""Tests for the shell-free, process-tree-owning subprocess adapter.

Why these tests contain no ``time.sleep`` synchronisation
---------------------------------------------------------

An earlier revision of the process-tree tests gave the spawned parent a 0.4
second wall-clock budget in which to boot, spawn a grandchild and touch a marker
file, and then asserted that the marker existed. That number was not part of any
contract; it was a guess about how long cold Python interpreters need on the
slowest machine that would ever run the suite. On Windows the adapter interposes
a stdin-blocked supervisor, so the guess had to cover three interpreter
start-ups, and it lost often enough under load to red the required
``cross-platform-smoke`` gate on unrelated pull requests. A required gate that
reports noise teaches reviewers to re-run it instead of to read it, which costs
far more than the test is worth.

The same guess also sat in this module's shared request helper as a five second
default deadline. Under the same load the three tests that only need a child to
run to completion — the stdin/cwd/environment test and both output-limit tests —
died on that deadline rather than on anything they assert.

Every budget here is now classified by whether it must expire, and a green run
pays only the one that must. Note that enlarging a budget is the right answer for
one class and the wrong answer for the other, which is why they are separated
rather than tuned. Enlarging a *must-expire* budget is rejected: it is paid on
every green run and it only lowers the probability of the false red instead of
removing its cause. Enlarging a *must-not-expire* budget costs a green run
nothing at all — its only function is to convert a hang into a bounded failure —
so it should be far above any plausible real duration rather than close to it.
This module got that wrong once already: a single 30 second budget covered both
observation and cold process start-up, and at 2x CPU oversubscription the
Windows supervisor chain measurably exceeded it and reported a healthy runtime as
timing out. The start-up budget is now the long tier.

Borrowed
~~~~~~~~

* CPython's ``test.support`` timeout tiering (``SHORT_TIMEOUT`` /
  ``LONG_TIMEOUT``, scaled by its ``--timeout`` option). Its distinction is that
  a budget bounding *a wait for something that must happen* is generous, because
  it is only ever paid when the product is broken, while a budget that must
  *expire* is short, because it is paid on every green run. One number can never
  serve those roles; this module keeps three named constants, and CPython's two
  tiers on the must-not-expire side exist for the same reason this module needs
  them — CPython raised its own timeouts repeatedly because slow buildbots kept
  reporting healthy code as broken.
* The rendezvous idiom used throughout CPython's ``subprocess`` and
  ``multiprocessing`` tests: the child announces itself over a channel and the
  parent waits for that announcement rather than for a duration. Here the
  channel is a loopback socket that the descendant connects back to. The same
  connection doubles as a liveness channel, because the operating system closes
  a killed process's sockets, so descendant death is observed positively as
  end-of-file instead of being inferred from a marker file that failed to appear
  in time.
* The request/response shape of that rendezvous, from pytest-xdist's worker
  "ready" protocol and ``multiprocessing``'s ``Connection`` handshake: the
  descendant waits to be acknowledged before it reports readiness onwards,
  because a send does not imply a receive. A connection the server has not
  accepted yet lives only in the listen backlog and an abortive close discards
  it, so a one-way announcement would let a healthy process-tree kill erase the
  evidence that the descendant ever existed.

Rejected
~~~~~~~~

* Enlarging the 0.4 second must-expire budget. That lowers the probability of a
  false red without removing its cause — wall-clock duration used as a
  synchronisation primitive — and every second added is paid on every green run
  of a required gate.
* Calibrating any budget from a measured interpreter start-up. It is still a
  guess, merely a better-informed one, and it is wrong the moment the machine is
  loaded by something the calibration did not observe. The must-not-expire
  budgets are deliberately far above the measurement rather than fitted to it.
* ``pytest-timeout``'s watchdog. Bounding how long a hung test may block is a
  useful backstop, but it is not a synchronisation primitive: it cannot
  distinguish "the descendant was never created" from "the descendant was
  created and correctly killed", which is exactly the distinction these tests
  exist to make.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from graph_skill_runtime.adapters import process as process_adapter
from graph_skill_runtime.adapters.process import SubprocessProcessRunner
from graph_skill_runtime.adapters.windows_job import WindowsJob
from graph_skill_runtime.ports.process import (
    ProcessCancelledError,
    ProcessOutputLimitError,
    ProcessRequest,
    ProcessTimedOutError,
)

# Two budgets that must never expire, split by what they have to cover. Both are
# generous on purpose: a green run pays neither, so their only job is to turn a
# hang into a bounded failure, and sizing either one tightly buys nothing.
#
# The names and the two values come from CPython ``test.support``'s
# ``SHORT_TIMEOUT`` (30s) and ``LONG_TIMEOUT`` (5 minutes), which exist for the
# same reason: CPython raised its own timeouts repeatedly because slow buildbots
# were reporting healthy code as broken.
#
# Bounds an observation whose cause has already happened — the tree has just been
# killed and the operating system only has to close a socket.
_OBSERVATION_TIMEOUT_SECONDS = 30.0

# Bounds a wait that must cover cold process start-up on an arbitrarily loaded
# machine, which on Windows means three interpreters behind the supervisor. This
# is not a guess about how long that takes; it is a bound far above any plausible
# value, because the wait ends on an event and not on the clock. 30s was NOT such
# a bound: at 2x CPU oversubscription this chain measurably exceeded it, so a
# healthy runtime was reported as timing out.
_STARTUP_TIMEOUT_SECONDS = 300.0

# Bounds a deadline that is required to elapse. Short on purpose: every green
# run pays it in full. It is never required to cover process start-up.
_MUST_EXPIRE_BUDGET_SECONDS = 0.05

# Long enough that a descendant which survives is still alive when the test
# checks, so survival is observed rather than waited out.
_DESCENDANT_LIFETIME_SECONDS = 3600.0

# An acceptor held back by far more than any real scheduling delay, used to
# assert that nothing depends on the test's own observer being prompt.
_SLOW_ACCEPTOR_DELAY_SECONDS = 2.0

_ANNOUNCEMENT = b"ready"

# One byte, so a non-empty ``recv(1)`` cannot return a short read.
_ACKNOWLEDGEMENT = b"k"

# Announce over the rendezvous socket, wait to be acknowledged, and only then
# announce over stdout for a parent that waits. Printing before the
# acknowledgement would make the stdout line mean "the announcement was sent",
# which the parent cannot act on: a connection that the server has not accepted
# yet lives only in the listen backlog, and an abortive close — which is what a
# healthy Job Object or process-group kill produces — discards it, so the server
# would never see the descendant that really did exist. The acknowledgement
# closes the handshake, so the stdout line means "the server has accepted this
# connection and holds it".
#
# SIGTERM is ignored so the POSIX termination path must escalate to SIGKILL
# rather than being satisfied by a cooperative child.
_DESCENDANT_ANNOUNCES_ITSELF_THEN_BLOCKS = (
    "import signal, socket, sys, time\n"
    "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
    "rendezvous = socket.create_connection(('127.0.0.1', int(sys.argv[1])))\n"
    f"rendezvous.sendall({_ANNOUNCEMENT!r})\n"
    f"if rendezvous.recv(1) != {_ACKNOWLEDGEMENT!r}:\n"
    "    raise SystemExit('rendezvous did not acknowledge the announcement')\n"
    "print('announced', flush=True)\n"
    f"time.sleep({_DESCENDANT_LIFETIME_SECONDS})\n"
)

_PARENT_SPAWNS_DESCENDANT_THEN_BLOCKS = (
    "import subprocess, sys, time\n"
    "subprocess.Popen([sys.executable, '-c', sys.argv[2], sys.argv[1]])\n"
    f"time.sleep({_DESCENDANT_LIFETIME_SECONDS})\n"
)

# Exits only after the descendant has announced itself, so "the parent finished
# while a descendant lingers" is established by a handshake, not by a race.
_PARENT_WAITS_FOR_DESCENDANT_THEN_EXITS = (
    "import subprocess, sys\n"
    "descendant = subprocess.Popen(\n"
    "    [sys.executable, '-c', sys.argv[2], sys.argv[1]], stdout=subprocess.PIPE\n"
    ")\n"
    "assert descendant.stdout is not None\n"
    "descendant.stdout.readline()\n"
)


class _DescendantRendezvous:
    """A loopback channel a descendant announces itself on and dies on.

    The exchange is a two-way handshake, not a one-way report: the descendant
    sends an announcement and the acceptor answers with an acknowledgement.
    Both halves are load-bearing. The announcement proves a descendant reached
    the rendezvous under its own steam; the acknowledgement is what lets the
    descendant tell anyone else that the *server* has the connection, which a
    one-way send cannot establish — until the server accepts, the connection
    exists only in the listen backlog, and an abortive close discards it.

    Borrowed from the ordinary request/response rendezvous shape used by
    pytest-xdist's worker "ready" protocol and by ``multiprocessing``'s
    ``Connection`` handshake: a peer that must gate later work on "you have me"
    waits for the other side to say so, rather than assuming that sending
    implies receiving.

    The acceptor also runs on its own thread so the announcement is consumed
    while the descendant is still alive; this test must not trade the start-up
    race it removes for a shutdown race.
    """

    def __init__(self, *, accept_delay_seconds: float = 0.0) -> None:
        self._listener = socket.create_server(("127.0.0.1", 0), backlog=1)
        self._listener.settimeout(_STARTUP_TIMEOUT_SECONDS)
        self._accept_delay_seconds = accept_delay_seconds
        self._connection: socket.socket | None = None
        self.announced = threading.Event()
        self._acceptor = threading.Thread(target=self._accept, daemon=True)
        self._acceptor.start()

    @property
    def port(self) -> int:
        return int(self._listener.getsockname()[1])

    def _accept(self) -> None:
        # A deliberately late acceptor stands in for an ordinary scheduling
        # delay on a loaded CI runner. Nothing outside this class may depend on
        # the acceptor being prompt.
        time.sleep(self._accept_delay_seconds)
        try:
            connection, _ = self._listener.accept()
        except OSError:
            return
        connection.settimeout(_STARTUP_TIMEOUT_SECONDS)
        received = bytearray()
        while len(received) < len(_ANNOUNCEMENT):
            try:
                chunk = connection.recv(len(_ANNOUNCEMENT) - len(received))
            except OSError:
                return
            if not chunk:
                return
            received.extend(chunk)
        if bytes(received) != _ANNOUNCEMENT:
            return
        # Register before acknowledging: if the descendant is killed between the
        # two, the connection this test reads its death from is already held.
        self._connection = connection
        self.announced.set()
        try:
            connection.sendall(_ACKNOWLEDGEMENT)
        except OSError:
            return

    def assert_descendant_is_gone(self) -> None:
        """Fail unless the announced descendant's socket has been closed."""
        assert self.announced.wait(_OBSERVATION_TIMEOUT_SECONDS), (
            "no descendant ever announced itself, so this run is no evidence "
            "about descendant cleanup"
        )
        connection = self._connection
        assert connection is not None
        # The socket carried a start-up-tier timeout while it was waiting for a
        # descendant to boot and announce itself. That phase is over: the tree
        # has already been told to die, so this read only waits for the kernel
        # to close a socket. Drop to the observation tier, or a runtime that
        # really does leak descendants would take five minutes per test to say
        # so.
        connection.settimeout(_OBSERVATION_TIMEOUT_SECONDS)
        try:
            remainder = connection.recv(64)
        except ConnectionResetError:
            # A Win32 job-object kill may abort the connection instead of
            # closing it gracefully; either way the peer no longer exists.
            return
        except TimeoutError as error:
            raise AssertionError(
                "the descendant still holds its rendezvous connection, so the "
                "runtime left it running"
            ) from error
        assert remainder == b"", (
            "the descendant kept talking after the runtime claimed to have "
            "terminated its process tree"
        )

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._listener.close()
        self._acceptor.join(timeout=_OBSERVATION_TIMEOUT_SECONDS)


@contextmanager
def _descendant_rendezvous(
    *,
    accept_delay_seconds: float = 0.0,
) -> Iterator[_DescendantRendezvous]:
    rendezvous = _DescendantRendezvous(accept_delay_seconds=accept_delay_seconds)
    try:
        yield rendezvous
    finally:
        rendezvous.close()


class _DeadlineArmedByRendezvous:
    """A ``time`` stand-in that arms the runner's deadline on a real event.

    ``SubprocessProcessRunner`` starts its deadline before it spawns anything,
    so a caller cannot ask it to "expire one moment after the descendant is
    alive"; the budget it is given must also cover process start-up, which is
    the unbounded quantity that made the old test flaky. Substituting the
    adapter's clock reference removes the guess: the clock reports that no time
    has passed until the descendant has announced itself, and reports the budget
    as spent from that moment on. Everything else stays real — the process tree,
    the termination path, the raised ``ProcessTimedOutError`` — and every other
    attribute, notably ``sleep`` used by the POSIX termination path, is
    delegated to the real module.

    Borrowed from asyncio's ``TestLoop`` virtual clock, which lets a test decide
    *when* a deadline is reached while refusing to guess *how long* a real event
    takes. That the real clock also drives this deadline is proven separately by
    ``test_timeout_is_raised_when_the_real_deadline_expires``.

    A real-time backstop of one rendezvous budget turns an environment in which
    the descendant can never reach loopback into a bounded failure rather than a
    hang. A green run never reaches it.
    """

    def __init__(self, announced: threading.Event, budget_seconds: float) -> None:
        self._announced = announced
        self._budget_seconds = budget_seconds
        self._real_start = time.monotonic()

    def __getattr__(self, name: str) -> Any:
        return getattr(time, name)

    def monotonic(self) -> float:
        waited_too_long = (
            time.monotonic() - self._real_start > _STARTUP_TIMEOUT_SECONDS
        )
        if self._announced.is_set() or waited_too_long:
            return self._budget_seconds * 2.0
        return 0.0


def _request(
    tmp_path: Path,
    *argv: str,
    stdin: str | None = None,
    # Almost every test here is about something other than the deadline, so its
    # deadline must not expire. ``ProcessRequest`` requires a positive one, so
    # those tests take the rendezvous budget: generous, never paid by a green
    # run, and present only so a hung child cannot hang the suite. Only a test
    # whose subject *is* the deadline passes the must-expire budget instead.
    timeout_seconds: float = _STARTUP_TIMEOUT_SECONDS,
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


def test_timeout_is_raised_when_the_real_deadline_expires(tmp_path: Path) -> None:
    """The real monotonic clock drives ``ProcessTimedOutError``.

    A must-expire budget is only required to be shorter than the child's
    lifetime. A child that has not finished booting has certainly not exited, so
    this assertion has no start-up race to lose and the budget stays small.
    """
    request = _request(
        tmp_path,
        sys.executable,
        "-c",
        f"import time; time.sleep({_DESCENDANT_LIFETIME_SECONDS})",
        timeout_seconds=_MUST_EXPIRE_BUDGET_SECONDS,
    )

    with pytest.raises(ProcessTimedOutError):
        SubprocessProcessRunner().run(request)


def test_timeout_terminates_the_whole_process_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _descendant_rendezvous() as rendezvous:
        request = _request(
            tmp_path,
            sys.executable,
            "-c",
            _PARENT_SPAWNS_DESCENDANT_THEN_BLOCKS,
            str(rendezvous.port),
            _DESCENDANT_ANNOUNCES_ITSELF_THEN_BLOCKS,
            timeout_seconds=_MUST_EXPIRE_BUDGET_SECONDS,
        )
        monkeypatch.setattr(
            process_adapter,
            "time",
            _DeadlineArmedByRendezvous(
                rendezvous.announced,
                _MUST_EXPIRE_BUDGET_SECONDS,
            ),
        )

        with pytest.raises(ProcessTimedOutError):
            SubprocessProcessRunner().run(request)

        rendezvous.assert_descendant_is_gone()


@pytest.mark.parametrize(
    "accept_delay_seconds",
    [
        pytest.param(0.0, id="prompt-acceptor"),
        pytest.param(_SLOW_ACCEPTOR_DELAY_SECONDS, id="slow-acceptor"),
    ],
)
def test_successful_parent_exit_also_cleans_up_lingering_descendants(
    tmp_path: Path,
    accept_delay_seconds: float,
) -> None:
    """Cleanup after a normal parent exit, whether or not the observer is prompt.

    This is the one path whose kill is triggered by the descendant's own
    announcement reaching the parent, so it is the path that would break if the
    announcement did not imply "the server holds this connection". The
    slow-acceptor case pins that down: with a one-way announcement the runtime
    kills the tree while the connection is still in the listen backlog, the
    acceptor finds nothing, and a healthy runtime is reported as broken. The
    timeout path is immune by construction — its deadline is armed *by* the
    acceptor, so a late acceptor only delays the kill.
    """
    with _descendant_rendezvous(
        accept_delay_seconds=accept_delay_seconds,
    ) as rendezvous:
        result = SubprocessProcessRunner().run(
            _request(
                tmp_path,
                sys.executable,
                "-c",
                _PARENT_WAITS_FOR_DESCENDANT_THEN_EXITS,
                str(rendezvous.port),
                _DESCENDANT_ANNOUNCES_ITSELF_THEN_BLOCKS,
                # The injected observer delay is test scaffolding, not product
                # latency, so it is added to the budget instead of silently
                # eating into it. Both cases then get the same real headroom.
                timeout_seconds=_STARTUP_TIMEOUT_SECONDS + accept_delay_seconds,
            )
        )

        assert result.exit_code == 0
        rendezvous.assert_descendant_is_gone()


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
        f"import time; time.sleep({_DESCENDANT_LIFETIME_SECONDS})",
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
    if sys.platform != "win32":
        def missing_process_group(_process_id: int, _signal: int) -> None:
            raise ProcessLookupError

        monkeypatch.setattr(os, "killpg", missing_process_group)
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


def test_posix_group_permission_fallback_signals_only_owned_members(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[tuple[int, int]] = []

    def denied_group_signal(_process_group_id: int, _signal: int) -> None:
        raise PermissionError

    monkeypatch.setitem(os.__dict__, "killpg", denied_group_signal)
    monkeypatch.setattr(
        process_adapter,
        "_posix_process_group_members",
        lambda process_group_id: (41, 43) if process_group_id == 37 else (),
    )
    monkeypatch.setattr(
        os,
        "kill",
        lambda process_id, requested_signal: observed.append(
            (process_id, requested_signal)
        ),
    )

    assert process_adapter._signal_posix_process_group(37, 15) is True
    assert observed == [(41, 15), (43, 15)]
