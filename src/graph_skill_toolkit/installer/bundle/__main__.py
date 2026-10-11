"""Build a toolkit from this source tree's explicit installer modules."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bundle import main  # noqa: E402

main()
