"""Write the FastAPI OpenAPI document used for frontend transport generation."""

from __future__ import annotations

import json
from pathlib import Path

from app.main import app


def main() -> None:
    output = Path(__file__).resolve().parents[1] / "openapi.json"
    output.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
