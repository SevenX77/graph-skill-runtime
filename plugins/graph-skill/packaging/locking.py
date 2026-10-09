"""Process-owned installer serialization and recovery of abandoned PID records."""

from __future__ import annotations

import ctypes
import os
from contextlib import contextmanager
from pathlib import Path

from ownership import InstallError, plain_path, read_bytes


def process_running(pid: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except (PermissionError, OverflowError):
            return True
        return True
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        if ctypes.get_last_error() == 87:  # ERROR_INVALID_PARAMETER: PID does not exist
            return False
        return True  # Inaccessible ownership remains protected.
    try:
        code = ctypes.c_uint32()
        if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == 259  # STILL_ACTIVE
    finally:
        kernel.CloseHandle(handle)


def acquire(handle: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(handle, 0, os.SEEK_SET)
        msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def release(handle: int) -> None:
    if os.name == "nt":
        import msvcrt

        os.lseek(handle, 0, os.SEEK_SET)
        msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def installer_lock(state: Path, notify=lambda message: None):
    plain_path(state)
    state.mkdir(parents=True, exist_ok=True)
    guard, marker = state / "installer.guard", state / "installer.lock"
    plain_path(guard)
    plain_path(marker)
    handle = os.open(guard, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    locked = False
    try:
        try:
            acquire(handle)
            locked = True
        except OSError as exc:
            raise InstallError("Another installer is running. Wait for it to finish, then retry the same command.") from exc
        # Keep this inode permanently. Unlinking an advisory lock admits a second
        # owner through a new inode while another process still holds the old one.
        os.write(handle, b"0")
        previous = read_bytes(marker)
        if previous is not None:
            try:
                text = previous.decode("ascii").strip()
                if not text.isdecimal() or not 0 < int(text) <= 0xFFFFFFFF:
                    raise ValueError("invalid PID")
                pid = int(text)
            except (UnicodeError, ValueError) as exc:
                raise InstallError(f"Cannot identify the owner of {marker}; preserved. Check the file and running installers before retrying.") from exc
            if process_running(pid):
                raise InstallError(f"Installer process {pid} is still running or inaccessible. Wait for it to finish, then retry the same command.")
            if read_bytes(marker) != previous:
                raise InstallError("Installer ownership changed during recovery; preserved. Retry after the other installer finishes.")
            marker.unlink()
            notify("Recovered an interrupted installation; its previous process has exited.")
        content = str(os.getpid()).encode("ascii")
        try:
            descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise InstallError("Another installer started during recovery. Wait for it to finish, then retry.") from exc
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
            yield
        finally:
            if read_bytes(marker) != content:
                raise InstallError("Installer ownership record changed; preserved for inspection.")
            marker.unlink()
    finally:
        if locked:
            release(handle)
        os.close(handle)
