"""Private, session-scoped persistence for the optional hook adapter."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import tempfile

from frontdoor.intent_lock import IntentLock, lock_from_dict, lock_to_dict


class StateError(RuntimeError):
    """The adapter state cannot be safely read or written."""


def state_path(state_root: Path, session_id: str) -> Path:
    """Return a traversal-safe path without retaining the raw session id."""

    digest = sha256(session_id.encode("utf-8")).hexdigest()
    return state_root / f"{digest}.json"


def _claim_path(state_root: Path, session_id: str) -> Path:
    digest = sha256(session_id.encode("utf-8")).hexdigest()
    return state_root / f".{digest}.pending"


def _validate_existing_root(state_root: Path, *, missing_ok: bool) -> bool:
    try:
        root_stat = state_root.lstat()
    except FileNotFoundError:
        if missing_ok:
            return False
        raise StateError(f"state root does not exist: {state_root}")
    except OSError as error:
        raise StateError(f"unable to inspect state root: {error}") from error
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        raise StateError(f"state root is not a real directory: {state_root}")
    permissions = stat.S_IMODE(root_stat.st_mode)
    if permissions != 0o700:
        raise StateError(
            f"state root permissions must be 0700, found {permissions:04o}"
        )
    return True


def _prepare_root(state_root: Path) -> None:
    try:
        created = False
        try:
            state_root.mkdir(mode=0o700, parents=True, exist_ok=False)
            created = True
        except FileExistsError:
            pass
        if created:
            state_root.chmod(0o700)
        _validate_existing_root(state_root, missing_ok=False)
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

    if not _validate_existing_root(state_root, missing_ok=True):
        return None
    path = state_path(state_root, session_id)
    try:
        try:
            path_stat = path.lstat()
        except FileNotFoundError:
            return None
        if stat.S_ISLNK(path_stat.st_mode) or not stat.S_ISREG(path_stat.st_mode):
            raise ValueError("state path is not a real regular file")
        permissions = stat.S_IMODE(path_stat.st_mode)
        if permissions != 0o600:
            raise ValueError(
                f"state file permissions must be 0600, found {permissions:04o}"
            )
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError("state root value must be an object")
        return lock_from_dict(value)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise StateError(f"invalid intent-lock state: {error}") from error


def delete_session_lock(state_root: Path, session_id: str) -> None:
    """Delete only the hashed state file for one session."""

    if not _validate_existing_root(state_root, missing_ok=True):
        return
    path = state_path(state_root, session_id)
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        raise StateError(f"unable to delete intent-lock state: {error}") from error


def claim_session_tool(state_root: Path, session_id: str) -> bool:
    """Atomically claim the one pending tool slot without retrying."""

    _prepare_root(state_root)
    path = _claim_path(state_root, session_id)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags, 0o600)
        os.close(descriptor)
        path.chmod(0o600)
        return True
    except FileExistsError:
        return False
    except OSError as error:
        raise StateError(f"unable to claim pending tool state: {error}") from error


def release_session_tool_claim(state_root: Path, session_id: str) -> None:
    """Release only this session's hashed pending-tool marker."""

    if not _validate_existing_root(state_root, missing_ok=True):
        return
    try:
        _claim_path(state_root, session_id).unlink(missing_ok=True)
    except OSError as error:
        raise StateError(f"unable to release pending tool state: {error}") from error
