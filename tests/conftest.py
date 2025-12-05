"""
Test configuration for tg-wp-bridge.

We ensure the project root is on sys.path so `import tg_wp_bridge`
works even without installing the package.

This keeps `uv run pytest` and `pytest` both happy in a "no-install" dev setup.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_project_root_on_syspath() -> None:
    # tests/ directory
    here = Path(__file__).resolve()
    # project root = parent of tests/
    project_root = here.parent.parent

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_ensure_project_root_on_syspath()
# == end/tests/conftest.py ==
