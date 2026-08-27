"""Local immutable run-request snapshot storage."""

from __future__ import annotations

import os
import uuid
from pathlib import Path

from pydantic import ValidationError

from graph_skill_runtime.domain.models import RunRequest


class LocalRunSnapshotStore:
    """Write one canonical request JSON file below the resolved state root."""

    _FILENAME = "request.json"

    @staticmethod
    def _run_directory(state_root: Path, run_id: str) -> Path:
        if not run_id or run_id in {".", ".."} or any(separator in run_id for separator in ("/", "\\")):
            raise ValueError("run_id must be one path segment")
        return state_root / "runs" / run_id

    def save(self, request: RunRequest) -> str:
        state_root = Path(request.profile.state_root)
        run_directory = self._run_directory(state_root, request.run_id)
        run_directory.mkdir(parents=True, exist_ok=True)
        destination = run_directory / self._FILENAME
        temporary = run_directory / f".{self._FILENAME}.{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                stream.write(request.model_dump_json(indent=2) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            try:
                # A same-filesystem hard link is an atomic create-if-absent. It
                # avoids os.replace(), whose overwrite behavior would make a
                # supposedly immutable run snapshot mutable under concurrency.
                os.link(temporary, destination)
            except FileExistsError:
                existing = self.load(state_root, request.run_id)
                if existing != request:
                    raise ValueError(
                        f"run snapshot {destination} already exists with different content"
                    ) from None
        finally:
            if temporary.exists():
                temporary.unlink()
        return str(destination)

    def load(self, state_root: Path, run_id: str) -> RunRequest:
        source = self._run_directory(state_root.resolve(strict=False), run_id) / self._FILENAME
        try:
            return RunRequest.model_validate_json(source.read_text(encoding="utf-8-sig"))
        except (OSError, ValidationError) as exc:
            raise ValueError(f"cannot load run snapshot {source}: {exc}") from exc
