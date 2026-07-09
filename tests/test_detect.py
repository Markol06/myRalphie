"""Tests for project command auto-detection."""
import json
from pathlib import Path

from ralph.detect import detect_commands


def test_python_project_with_ruff(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 88\n")
    detected = detect_commands(tmp_path)
    assert detected["test_command"] == "pytest -q"
    assert detected["lint_command"] == "ruff check ."


def test_python_project_without_ruff(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'x'\n")
    detected = detect_commands(tmp_path)
    assert detected["test_command"] == "pytest -q"
    assert "lint_command" not in detected


def test_node_project(tmp_path: Path):
    (tmp_path / "package.json").write_text(json.dumps({
        "scripts": {"test": "vitest", "lint": "eslint .", "build": "vite build"}
    }))
    detected = detect_commands(tmp_path)
    assert detected["test_command"] == "npm test"
    assert detected["lint_command"] == "npm run lint"
    assert detected["build_command"] == "npm run build"


def test_node_project_without_scripts(tmp_path: Path):
    (tmp_path / "package.json").write_text("{}")
    assert detect_commands(tmp_path) == {}


def test_rust_and_go(tmp_path: Path):
    (tmp_path / "Cargo.toml").write_text("[package]\nname = 'x'\n")
    detected = detect_commands(tmp_path)
    assert detected["test_command"] == "cargo test"
    assert detected["build_command"] == "cargo build"

    go_dir = tmp_path / "go"
    go_dir.mkdir()
    (go_dir / "go.mod").write_text("module x\n")
    detected = detect_commands(go_dir)
    assert detected["test_command"] == "go test ./..."


def test_empty_project(tmp_path: Path):
    assert detect_commands(tmp_path) == {}
