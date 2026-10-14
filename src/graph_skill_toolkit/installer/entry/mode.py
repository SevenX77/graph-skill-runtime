"""Trusted script-directory bootstrap for isolated source-mode calls."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mode import main  # noqa: E402

raise SystemExit(main())
