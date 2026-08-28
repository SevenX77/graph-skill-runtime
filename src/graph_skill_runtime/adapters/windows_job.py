"""Small Win32 Job Object owner for one supervised process tree."""

from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any, cast

_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
_PROCESS_TERMINATE = 0x0001
_PROCESS_SET_QUOTA = 0x0100


class _IoCounters(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_ulonglong),
        ("WriteOperationCount", ctypes.c_ulonglong),
        ("OtherOperationCount", ctypes.c_ulonglong),
        ("ReadTransferCount", ctypes.c_ulonglong),
        ("WriteTransferCount", ctypes.c_ulonglong),
        ("OtherTransferCount", ctypes.c_ulonglong),
    ]


class _BasicLimitInformation(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _ExtendedLimitInformation(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _BasicLimitInformation),
        ("IoInfo", _IoCounters),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def _kernel32() -> Any:
    if sys.platform != "win32":
        raise OSError("Windows Job Objects are only available on Windows")
    loader = ctypes.WinDLL
    return loader("kernel32", use_last_error=True)


def _win32_error(operation: str) -> OSError:
    # Platform stubs intentionally omit these APIs on POSIX even though this
    # Windows adapter is type-checked there; _kernel32() guards every caller.
    get_last_error = cast(Callable[[], int], ctypes.__dict__["get_last_error"])
    format_error = cast(Callable[[int], str], ctypes.__dict__["FormatError"])
    error_code = get_last_error()
    return OSError(error_code, f"{operation} failed: {format_error(error_code)}")


@dataclass
class WindowsJob:
    """Own a process hierarchy with kill-on-close semantics."""

    _handle: int
    _closed: bool = False

    @classmethod
    def create(cls) -> WindowsJob:
        kernel32 = _kernel32()
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise _win32_error("CreateJobObjectW")
        numeric_handle = cast(int, handle)
        information = _ExtendedLimitInformation()
        information.BasicLimitInformation.LimitFlags = (
            _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        )
        configured = kernel32.SetInformationJobObject(
            wintypes.HANDLE(numeric_handle),
            _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(information),
            ctypes.sizeof(information),
        )
        if not configured:
            kernel32.CloseHandle(wintypes.HANDLE(numeric_handle))
            raise _win32_error("SetInformationJobObject")
        return cls(numeric_handle)

    def assign(self, process_id: int) -> None:
        kernel32 = _kernel32()
        kernel32.OpenProcess.restype = wintypes.HANDLE
        process_handle = kernel32.OpenProcess(
            _PROCESS_TERMINATE | _PROCESS_SET_QUOTA,
            False,
            process_id,
        )
        if not process_handle:
            raise _win32_error("OpenProcess")
        try:
            assigned = kernel32.AssignProcessToJobObject(
                wintypes.HANDLE(self._handle),
                wintypes.HANDLE(process_handle),
            )
            if not assigned:
                raise _win32_error("AssignProcessToJobObject")
        finally:
            kernel32.CloseHandle(wintypes.HANDLE(process_handle))

    def terminate(self) -> None:
        if self._closed:
            return
        kernel32 = _kernel32()
        terminated = kernel32.TerminateJobObject(wintypes.HANDLE(self._handle), 1)
        if not terminated:
            raise _win32_error("TerminateJobObject")

    def close(self) -> None:
        if self._closed:
            return
        kernel32 = _kernel32()
        self._closed = True
        if not kernel32.CloseHandle(wintypes.HANDLE(self._handle)):
            raise _win32_error("CloseHandle")
