"""Trusted script-directory bootstrap for Python isolated-mode lifecycle calls."""

import sys
from pathlib import Path

# -I intentionally excludes cwd and script-directory imports. Add only this
# packaged directory, never the invoking project or ambient PYTHONPATH.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from install import main  # noqa: E402

raise SystemExit(main())
