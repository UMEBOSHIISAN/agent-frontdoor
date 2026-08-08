"""Behavior tests for private, session-scoped hook state."""

from __future__ import annotations

import json
from pathlib import Path
import stat

import pytest

from frontdoor.intent_lock import derive_lock
from frontdoor_hooks.state import (
    StateError,
    delete_session_lock,
    load_session_lock,
    save_session_lock,
    state_path,
)


def _lock():
    lock = derive_lock("`codex mcp login cloudflare-api`")
    assert lock is not None
    return lock


def test_state_path_hashes_session_id_and_cannot_traverse(tmp_path: Path) -> None:
    session_id = "../../raw-session-id"

    path = state_path(tmp_path, session_id)

    assert path.parent == tmp_path
    assert path.suffix == ".json"
    assert "raw-session-id" not in path.name
    assert len(path.stem) == 64


def test_save_is_private_atomic_and_contains_only_contract(
    tmp_path: Path,
) -> None:
    session_id = "raw-session-id"
    lock = _lock()

    path = save_session_lock(tmp_path, session_id, lock)

    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    text = path.read_text(encoding="utf-8")
    assert session_id not in text
    assert "codex mcp login" not in text
    assert "transcript" not in text
    assert not list(tmp_path.glob("*.tmp"))
    assert load_session_lock(tmp_path, session_id) == lock


def test_missing_state_returns_none_and_delete_is_idempotent(
    tmp_path: Path,
) -> None:
    assert load_session_lock(tmp_path, "missing") is None

    delete_session_lock(tmp_path, "missing")
    path = save_session_lock(tmp_path, "session", _lock())
    delete_session_lock(tmp_path, "session")
    delete_session_lock(tmp_path, "session")

    assert not path.exists()


def test_invalid_state_fails_closed_instead_of_becoming_no_lock(
    tmp_path: Path,
) -> None:
    tmp_path.mkdir(mode=0o700, exist_ok=True)
    path = state_path(tmp_path, "session")
    path.write_text(json.dumps({"phase": "WANDER"}), encoding="utf-8")

    with pytest.raises(StateError, match="invalid intent-lock state"):
        load_session_lock(tmp_path, "session")


def test_state_inspection_error_is_translated_to_state_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def deny_inspection(_path: Path) -> bool:
        raise PermissionError("synthetic unreadable state path")

    monkeypatch.setattr(Path, "exists", deny_inspection)

    with pytest.raises(StateError, match="invalid intent-lock state"):
        load_session_lock(tmp_path, "session")


def test_state_root_file_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "not-a-directory"
    root.write_text("occupied", encoding="utf-8")

    with pytest.raises(StateError, match="state root"):
        save_session_lock(root, "session", _lock())


def test_existing_shared_state_root_is_rejected_without_chmod(tmp_path: Path) -> None:
    root = tmp_path / "shared"
    root.mkdir(mode=0o700)
    root.chmod(0o755)
    before = stat.S_IMODE(root.stat().st_mode)

    with pytest.raises(StateError, match="existing state root permissions"):
        save_session_lock(root, "session", _lock())

    assert stat.S_IMODE(root.stat().st_mode) == before
