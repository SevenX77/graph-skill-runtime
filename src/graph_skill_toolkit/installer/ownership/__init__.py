"""Product-owned file transactions; independent of the Python runtime package."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path


class InstallError(RuntimeError):
    pass


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def plain_path(path: Path) -> None:
    """Refuse redirects before reading or mutating installer-owned paths."""
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise InstallError(f"Path uses a symlink or reparse point: {item}")


def read_bytes(path: Path) -> bytes | None:
    plain_path(path)
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def read_json(path: Path) -> dict:
    raw = read_bytes(path)
    if raw is None:
        return {}
    try:
        result = json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeError) as exc:
        raise InstallError(f"Invalid JSON: {path}: {exc}") from exc
    if not isinstance(result, dict):
        raise InstallError(f"Expected a JSON object: {path}")
    return result


def replace(path: Path, before: bytes | None, after: bytes | None) -> None:
    if read_bytes(path) != before:
        raise InstallError(f"Concurrent change preserved: {path}")
    if before == after:
        return
    if after is None:
        path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    plain_path(path.parent)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        if before is not None:
            os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(handle, "wb") as stream:
            stream.write(after)
            stream.flush()
            os.fsync(stream.fileno())
        if read_bytes(path) != before:
            raise InstallError(f"Concurrent change preserved: {path}")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class Transaction:
    def __init__(self) -> None:
        self.changes: list[tuple[Path, bytes | None, bytes | None]] = []
        self.applied: list[tuple[Path, bytes | None, bytes | None]] = []

    def add(self, path: Path, before: bytes | None, after: bytes | None) -> None:
        if any(item[0] == path for item in self.changes):
            raise InstallError(f"Duplicate transaction owner: {path}")
        self.changes.append((path, before, after))

    def summary(self) -> list[dict]:
        return [
            {"path": str(path), "action": "remove" if after is None else "write"}
            for path, before, after in self.changes
            if before != after
        ]

    def apply(self) -> None:
        for path, before, _ in self.changes:
            if read_bytes(path) != before:
                raise InstallError(f"Concurrent change preserved: {path}")
        try:
            for path, before, after in self.changes:
                replace(path, before, after)
                self.applied.append((path, before, after))
        except BaseException:
            self.rollback()
            raise

    def rollback(self) -> None:
        failures = []
        for path, before, after in reversed(self.applied):
            try:
                replace(path, after, before)
            except (OSError, InstallError) as exc:
                failures.append(str(exc))
        self.applied.clear()
        if failures:
            raise InstallError("Rollback preserved concurrent changes: " + "; ".join(failures))
