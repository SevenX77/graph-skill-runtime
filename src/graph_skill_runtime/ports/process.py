"""Provider-neutral process execution contracts used by CLI adapters."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class CancellationProbe(Protocol):
    """Report cooperative cancellation without prescribing its owner."""

    def is_cancelled(self) -> bool: ...


@dataclass(frozen=True)
class ProcessRequest:
    """One shell-free child-process request."""

    argv: tuple[str, ...]
    cwd: Path
    environment: Mapping[str, str]
    stdin: str | None
    timeout_seconds: float
    max_output_bytes: int = 4 * 1024 * 1024


@dataclass(frozen=True)
class ProcessResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    process_id: int


ProcessStarted = Callable[[int], None]


class ProcessRunner(Protocol):
    """Run one process and own timeout/cancellation tree cleanup."""

    def run(
        self,
        request: ProcessRequest,
        *,
        cancellation: CancellationProbe | None = None,
        on_started: ProcessStarted | None = None,
    ) -> ProcessResult: ...


class ProcessExecutionError(RuntimeError):
    """Base class for failures whose argv may contain confidential input."""


class ProcessTimedOutError(ProcessExecutionError):
    def __init__(self, timeout_seconds: float) -> None:
        super().__init__(f"process exceeded its {timeout_seconds:g}s deadline")
        self.timeout_seconds = timeout_seconds


class ProcessCancelledError(ProcessExecutionError):
    pass


class ProcessOutputLimitError(ProcessExecutionError):
    def __init__(self, max_output_bytes: int) -> None:
        super().__init__(f"process output exceeded {max_output_bytes} bytes")
        self.max_output_bytes = max_output_bytes
