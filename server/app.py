"""
OpenEnv server entry point.

This module provides the main() function required by the OpenEnv spec
for `uv run server` and `openenv serve` to start the environment server.
"""
import sys
from pathlib import Path

# Ensure project root is on sys.path so imports work from server/ subdirectory
_project_root = str(Path(__file__).resolve().parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import uvicorn


def main(host: str = "0.0.0.0", port: int = 7860) -> None:
    """Start the Email Triage OpenEnv server."""
    uvicorn.run("app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
