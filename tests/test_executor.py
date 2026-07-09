"""Tests for executor helpers (no real claude process involved)."""
from ralph.executor import _to_text, _handle_stream_line


def test_to_text_handles_str_bytes_and_none():
    assert _to_text("hello") == "hello"
    assert _to_text(b"hello") == "hello"
    assert _to_text(None) == ""
    assert _to_text(b"\xff\xfe") != ""  # invalid utf-8 replaced, not raising


def test_stream_line_collects_result_event():
    final: dict = {}
    transcript: list[str] = []
    line = (
        '{"type": "result", "subtype": "success", "result": "RALPH_STATUS: ...",'
        ' "total_cost_usd": 0.42, "num_turns": 7,'
        ' "usage": {"input_tokens": 10, "output_tokens": 20}}'
    )
    _handle_stream_line(line, transcript, final)
    assert final["total_cost_usd"] == 0.42
    assert final["num_turns"] == 7


def test_stream_line_collects_assistant_text_and_tools():
    final: dict = {}
    transcript: list[str] = []
    line = json_assistant = (
        '{"type": "assistant", "message": {"content": ['
        '{"type": "text", "text": "Working on it"},'
        '{"type": "tool_use", "name": "Bash"}]}}'
    )
    _handle_stream_line(json_assistant, transcript, final)
    assert "Working on it" in transcript
    assert "[tool_use] Bash" in transcript
    assert final == {}


def test_stream_line_tolerates_non_json():
    final: dict = {}
    transcript: list[str] = []
    _handle_stream_line("not json at all", transcript, final)
    _handle_stream_line("", transcript, final)
    assert transcript == ["not json at all"]
