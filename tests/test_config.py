"""Tests for RalphConfig loading and env overrides."""
import json
from pathlib import Path

from ralph.config import RalphConfig


def test_defaults_when_no_file(tmp_path: Path):
    config = RalphConfig.load(tmp_path)
    assert config.chunk_size == 5
    assert config.model == ""


def test_unknown_keys_are_ignored(tmp_path: Path):
    (tmp_path / ".ralphrc").write_text(json.dumps({
        "chunk_size": 7,
        "branch_per_task": True,  # removed field from older versions
        "allowed_tools": ["Read"],  # removed field from older versions
    }))
    config = RalphConfig.load(tmp_path)
    assert config.chunk_size == 7


def test_env_overrides_secrets(tmp_path: Path, monkeypatch):
    (tmp_path / ".ralphrc").write_text(json.dumps({
        "telegram_token": "file-token",
    }))
    monkeypatch.setenv("RALPH_TELEGRAM_TOKEN", "env-token")
    monkeypatch.setenv("RALPH_TELEGRAM_CHAT_ID", "12345")
    config = RalphConfig.load(tmp_path)
    assert config.telegram_token == "env-token"
    assert config.telegram_chat_id == "12345"


def test_file_secrets_used_without_env(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("RALPH_TELEGRAM_TOKEN", raising=False)
    (tmp_path / ".ralphrc").write_text(json.dumps({
        "telegram_token": "file-token",
    }))
    config = RalphConfig.load(tmp_path)
    assert config.telegram_token == "file-token"
