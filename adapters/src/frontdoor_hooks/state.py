"""Private, session-scoped persistence for the optional hook adapter."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile

from frontdoor.intent_lock import IntentLock, lock_from_dict, lock_to_dict


class StateError(RuntimeError):
    """The adapter state cannot be safely read or written."""


def state_path(state_root: Path, session_id: str) -> Path:
    """Return a traversal-safe path without retaining the raw session id."""

    digest = sha256(session_id.encode("utf-8")).hexdigest()
    return state_root / f"{digest}.json"


def _prepare_root(state_root: Path) -> None:
    try:
        state_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not state_root.is_dir():
            raise StateError(f"state root is not a directory: {state_root}")
        state_root.chmod(0o700)
    except StateError:
        raise
    except OSError as error:
        raise StateError(f"unable to prepare state root: {error}") from error


def save_session_lock(
    state_root: Path,
    session_id: str,
    lock: IntentLock,
) -> Path:
    """Atomically save validated contract JSON with private permissions."""

    _prepare_root(state_root)
    destination = state_path(state_root, session_id)
    payload = json.dumps(
        lock_to_dict(lock),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=state_root,
            prefix=f".{destination.stem}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary_path.chmod(0o600)
        os.replace(temporary_path, destination)
        destination.chmod(0o600)
    except OSError as error:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
        raise StateError(f"unable to save intent-lock state: {error}") from error
    return destination


def load_session_lock(
    state_root: Path,
    session_id: str,
) -> IntentLock | None:
    """Load validated state; malformed state is an explicit failure."""

    path = state_path(state_root, session_id)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("state root value must be an object")
        return lock_from_dict(value)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise StateError(f"invalid intent-lock state: {error}") from error


def delete_session_lock(state_root: Path, session_id: str) -> None:
    """Delete only the hashed state file for one session."""

    path = state_path(state_root, session_id)
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        raise StateError(f"unable to delete intent-lock state: {error}") from error

