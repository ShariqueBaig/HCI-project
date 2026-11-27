"""Single-command launcher for AURA Affective Generative UI."""

from __future__ import annotations

import uvicorn


def main() -> None:
    print("\n  AURA — Affective Adaptive Workspace & Generative UI")
    print("  Starting server on http://127.0.0.1:8000\n")
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False, log_level="info")


if __name__ == "__main__":
    main()
