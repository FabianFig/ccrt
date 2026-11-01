"""Credential lookup for the CLI's UCDP fetch command."""

import os
from pathlib import Path

from dotenv import dotenv_values


def ucdp_api_key(env_file: str | Path | None = None) -> str | None:
    """Use the process environment first, then a local .env file.

    Reads only UCDP_API_KEY; it does not import the rest of the file into the
    process environment or expand variables inside the token.
    """
    key = os.environ.get("UCDP_API_KEY", "").strip()
    if key:
        return key
    path = Path(env_file) if env_file is not None else Path.cwd() / ".env"
    if not path.is_file():
        if env_file is not None:
            raise FileNotFoundError(f"environment file not found: {path}")
        return None
    return (dotenv_values(path, interpolate=False).get("UCDP_API_KEY") or "").strip() or None
