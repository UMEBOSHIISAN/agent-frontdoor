"""Behavior tests for private, session-scoped hook state."""

from __future__ import annotations

import json
from pathlib import Path
import stat

import pytest

from frontdoor.intent_lock import derive_lock
from frontdoor_hooks.state import (
    StateError,
    claim_session_tool,
    delete_session_lock,
    load_session_lock,
    release_session_tool_claim,
    save_session_lock,
    session_state_guard,
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


def test_pending_tool_claim_is_atomic_private_and_session_hashed(
    tmp_path: Path,
) -> None:
    session_id = "raw-session-id"

    assert claim_session_tool(tmp_path, session_id)
    assert not claim_session_tool(tmp_path, session_id)
    claims = list(tmp_path.glob("*.pending"))
    assert len(claims) == 1
    assert session_id not in claims[0].name
    assert stat.S_IMODE(claims[0].stat().st_mode) == 0o600
    assert claims[0].read_bytes() == b""

    release_session_tool_claim(tmp_path, session_id)
    assert not claims[0].exists()
    assert claim_session_tool(tmp_path, session_id)


def test_session_guard_is_private_persistent_and_session_hashed(
    tmp_path: Path,
) -> None:
    session_id = "raw-session-id"

    with session_state_guard(tmp_path, session_id):
        guards = list(tmp_path.glob("*.guard"))
        assert len(guards) == 1
        assert session_id not in guards[0].name
        assert stat.S_IMODE(guards[0].stat().st_mode) == 0o600

    assert guards[0].is_file()


def test_session_guard_rejects_exposed_existing_file(tmp_path: Path) -> None:
    with session_state_guard(tmp_path, "session"):
        guard = next(tmp_path.glob("*.guard"))
    guard.chmod(0o644)

    with pytest.raises(StateError, match="guard permissions"):
        with session_state_guard(tmp_path, "session"):
            pass


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
    original_lstat = Path.lstat

    def deny_inspection(path: Path):
        if path == tmp_path:
            raise PermissionError("synthetic unreadable state root")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", deny_inspection)

    with pytest.raises(StateError, match="state root"):
        load_session_lock(tmp_path, "session")


def test_unreadable_existing_state_root_is_not_treated_as_missing(
    tmp_path: Path,
) -> None:
    save_session_lock(tmp_path, "session", _lock())
    tmp_path.chmod(0)

    try:
        with pytest.raises(StateError, match="state root permissions"):
            load_session_lock(tmp_path, "session")
    finally:
        tmp_path.chmod(0o700)


def test_state_load_rejects_symlinked_root(tmp_path: Path) -> None:
    real_root = tmp_path / "real"
    save_session_lock(real_root, "session", _lock())
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(StateError, match="state root"):
        load_session_lock(linked_root, "session")


def test_state_delete_rejects_symlinked_root_without_deleting_target(
    tmp_path: Path,
) -> None:
    real_root = tmp_path / "real"
    path = save_session_lock(real_root, "session", _lock())
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(StateError, match="state root"):
        delete_session_lock(linked_root, "session")

    assert path.is_file()


def test_state_delete_rejects_shared_root_without_deleting_target(
    tmp_path: Path,
) -> None:
    root = tmp_path / "shared"
    path = save_session_lock(root, "session", _lock())
    root.chmod(0o755)

    try:
        with pytest.raises(StateError, match="state root permissions"):
            delete_session_lock(root, "session")
        assert path.is_file()
    finally:
        root.chmod(0o700)


def test_state_delete_is_a_noop_when_root_is_genuinely_absent(
    tmp_path: Path,
) -> None:
    delete_session_lock(tmp_path / "absent", "session")


def test_state_load_rejects_exposed_state_file(tmp_path: Path) -> None:
    path = save_session_lock(tmp_path, "session", _lock())
    path.chmod(0o644)

    with pytest.raises(StateError, match="state file permissions"):
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

    with pytest.raises(StateError, match="state root permissions"):
        save_session_lock(root, "session", _lock())

    assert stat.S_IMODE(root.stat().st_mode) == before
