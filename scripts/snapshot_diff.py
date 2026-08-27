#!/usr/bin/env python3
"""Normalize and compare runtime JSONL traces against a baseline."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

_UUID_RE = re.compile(
    r"^(?:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|[0-9a-f]{12}(?:-\d+)?)$",
    re.IGNORECASE,
)

_ID_FIELD_NAMES = frozenset(
    {
        "run_id",
        "thread_id",
        "sub_run_id",
        "group_key",
        "tool_call_id",
        "child_thread_id",
    }
)


def _looks_like_id(value: str) -> bool:
    if _UUID_RE.match(value):
        return True
    return re.match(r"^[0-9a-f]{12}-\d+$", value, re.IGNORECASE) is not None


def _normalise(obj: Any, uuid_map: dict[str, str], *, in_id_field: bool = False) -> Any:
    """Return a recursively normalized copy of an event value."""
    if isinstance(obj, str):
        if in_id_field or _looks_like_id(obj):
            return uuid_map.setdefault(obj, f"normalized_uuid_{len(uuid_map) + 1}")
        return obj

    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for key, value in obj.items():
            if key == "timestamp":
                continue
            out[key] = _normalise(value, uuid_map, in_id_field=(key in _ID_FIELD_NAMES))
        return out

    if isinstance(obj, list):
        return [_normalise(item, uuid_map) for item in obj]

    return obj


def _load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{idx}: invalid JSON — {exc}") from exc
    return events


def _normalise_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    uuid_map: dict[str, str] = {}
    return [_normalise(event, uuid_map) for event in events]


def _record(run_path: Path, out_path: Path) -> int:
    if not run_path.exists():
        print(f"[snapshot_diff] not found: {run_path}", file=sys.stderr)
        return 2
    normalised = _normalise_events(_load_events(run_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(normalised, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"[snapshot_diff] recorded {len(normalised)} events → {out_path}")
    return 0


def _diff(run_path: Path, baseline_path: Path) -> int:
    if not run_path.exists():
        print(f"[snapshot_diff] not found: {run_path}", file=sys.stderr)
        return 2
    if not baseline_path.exists():
        print(f"[snapshot_diff] not found: {baseline_path}", file=sys.stderr)
        return 2

    baseline_events = json.loads(baseline_path.read_text(encoding="utf-8"))
    run_events = _normalise_events(_load_events(run_path))
    if baseline_events == run_events:
        print(
            f"[snapshot_diff] OK — {len(run_events)} events match baseline "
            f"({baseline_path.name})"
        )
        return 0

    baseline_lines = json.dumps(baseline_events, indent=2, ensure_ascii=False).splitlines(
        keepends=True
    )
    run_lines = json.dumps(run_events, indent=2, ensure_ascii=False).splitlines(keepends=True)
    diff = difflib.unified_diff(
        baseline_lines,
        run_lines,
        fromfile=str(baseline_path),
        tofile=str(run_path),
        lineterm="",
    )
    sys.stdout.writelines(diff)
    sys.stdout.write("\n")
    print(
        f"[snapshot_diff] FAIL — baseline and run differ "
        f"(baseline={len(baseline_events)} events, run={len(run_events)})",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Normalize and diff a runtime JSONL trace against a baseline."
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    record = sub.add_parser("record", help="Save a normalized JSONL trace as a baseline.")
    record.add_argument("--run", required=True, type=Path, help="Path to the JSONL trace")
    record.add_argument("--out", required=True, type=Path, help="Output baseline JSON path")

    diff = sub.add_parser("diff", help="Diff a JSONL trace against a saved baseline.")
    diff.add_argument("--run", required=True, type=Path, help="Path to the JSONL trace")
    diff.add_argument("--baseline", required=True, type=Path, help="Path to baseline JSON")

    args = parser.parse_args(argv)
    if args.mode == "record":
        return _record(args.run, args.out)
    if args.mode == "diff":
        return _diff(args.run, args.baseline)
    return 2


if __name__ == "__main__":
    sys.exit(main())
