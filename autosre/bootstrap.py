"""Environment bootstrap — load `.env` before reading configuration."""

from __future__ import annotations


def load_env() -> None:
    """Load dotenv if available. Safe to call repeatedly."""
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
