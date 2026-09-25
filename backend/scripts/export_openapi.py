"""Write the API's OpenAPI schema to frontend/openapi.json (frontend types are generated from it).

Usage (from backend/):  python scripts/export_openapi.py
Then (from frontend/):  npm run gen:api
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import REPO_DIR  # noqa: E402
from app.main import app  # noqa: E402


def main() -> None:
    target = REPO_DIR / "frontend" / "openapi.json"
    target.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
