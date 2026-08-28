"""Cross-platform atomic publication without replacing an existing path."""

from __future__ import annotations

import ctypes
import errno
import os
import sys
from pathlib import Path

_AT_FDCWD = -100
_LINUX_RENAME_NOREPLACE = 1
_DARWIN_RENAME_EXCL = 0x00000004


def publish_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically rename ``source`` while failing if ``destination`` exists.

    Linux's ``renameat2(RENAME_NOREPLACE)`` and macOS's
    ``renamex_np(RENAME_EXCL)`` are the native exclusive-rename mechanisms.
    Windows rename already rejects an existing destination directory. Plain
    POSIX ``rename`` is deliberately not a fallback: on common filesystems it
    can replace an empty destination directory, violating migration's
    never-overwrite contract.
    """

    if sys.platform.startswith("linux"):
        _linux_publish(source, destination)
        return
    if sys.platform == "darwin":
        _darwin_publish(source, destination)
        return
    if os.name == "nt":
        os.rename(source, destination)
        return
    raise OSError(
        errno.ENOTSUP,
        "atomic no-replace directory publication is unsupported on this platform",
        destination,
    )


def _linux_publish(source: Path, destination: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameat2 = libc.renameat2
    except AttributeError as exc:
        raise OSError(
            errno.ENOTSUP,
            "renameat2 is unavailable; refusing a potentially replacing rename",
            destination,
        ) from exc
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        _AT_FDCWD,
        os.fsencode(source),
        _AT_FDCWD,
        os.fsencode(destination),
        _LINUX_RENAME_NOREPLACE,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), destination)


def _darwin_publish(source: Path, destination: Path) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    renamex_np = libc.renamex_np
    renamex_np.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    renamex_np.restype = ctypes.c_int
    result = renamex_np(
        os.fsencode(source),
        os.fsencode(destination),
        _DARWIN_RENAME_EXCL,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(error_number, os.strerror(error_number), destination)


__all__ = ["publish_directory_no_replace"]
