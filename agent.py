"""Thin CLI entry point — delegates to autosre.agent.main.

Usage:
    python agent.py db
    python agent.py disk --simulate
    python agent.py --list
"""

from __future__ import annotations

import sys

from autosre.bootstrap import load_env

load_env()

from autosre.agent import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
