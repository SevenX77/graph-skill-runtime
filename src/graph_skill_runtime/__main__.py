"""Allow ``python -m graph_skill_runtime`` to run the stable ``gskill`` CLI."""

from __future__ import annotations

from graph_skill_runtime.adapters.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
