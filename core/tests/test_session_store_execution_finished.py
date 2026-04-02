"""Tests for SessionStore.is_session_execution_finished."""

import json
from pathlib import Path

import pytest

from framework.storage.session_store import SessionStore


def _write_state(base: Path, session_id: str, status: str) -> None:
    store = SessionStore(base)
    d = store.get_session_path(session_id)
    d.mkdir(parents=True, exist_ok=True)
    path = d / "state.json"
    path.write_text(
        json.dumps({"session_id": session_id, "status": status}),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("completed", True),
        ("failed", True),
        ("cancelled", True),
        ("active", False),
        ("paused", False),
    ],
)
def test_is_session_execution_finished(tmp_path: Path, status: str, expected: bool) -> None:
    sid = "session_20990101_000000_aaaaaaaa"
    _write_state(tmp_path, sid, status)
    store = SessionStore(tmp_path)
    assert store.is_session_execution_finished(sid) is expected


def test_is_session_execution_finished_missing_file(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    assert store.is_session_execution_finished("session_20990101_000000_bbbbbbbb") is False


def test_is_session_execution_finished_invalid_json(tmp_path: Path) -> None:
    store = SessionStore(tmp_path)
    sid = "session_20990101_000000_cccccccc"
    d = store.get_session_path(sid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "state.json").write_text("{not json", encoding="utf-8")
    assert store.is_session_execution_finished(sid) is False
