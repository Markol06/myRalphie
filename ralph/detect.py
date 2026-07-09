"""Auto-detect test/lint/build commands from common project files."""
from __future__ import annotations

import json
from pathlib import Path


def detect_commands(project_root: Path) -> dict[str, str]:
    """Best-effort detection; returns only the keys it is confident about."""
    detected: dict[str, str] = {}

    pyproject = project_root / "pyproject.toml"
    if pyproject.exists():
        text = pyproject.read_text(encoding="utf-8", errors="replace")
        detected["test_command"] = "pytest -q"
        has_ruff = (
            "ruff" in text
            or (project_root / "ruff.toml").exists()
            or (project_root / ".ruff.toml").exists()
        )
        if has_ruff:
            detected["lint_command"] = "ruff check ."

    package_json = project_root / "package.json"
    if package_json.exists():
        try:
            scripts = json.loads(
                package_json.read_text(encoding="utf-8", errors="replace")
            ).get("scripts", {})
        except json.JSONDecodeError:
            scripts = {}
        if "test" in scripts:
            detected.setdefault("test_command", "npm test")
        if "lint" in scripts:
            detected.setdefault("lint_command", "npm run lint")
        if "build" in scripts:
            detected.setdefault("build_command", "npm run build")

    if (project_root / "Cargo.toml").exists():
        detected.setdefault("test_command", "cargo test")
        detected.setdefault("build_command", "cargo build")

    if (project_root / "go.mod").exists():
        detected.setdefault("test_command", "go test ./...")
        detected.setdefault("build_command", "go build ./...")

    return detected
