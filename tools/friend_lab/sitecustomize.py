"""Fail-closed Python audit guard loaded only by the friend-lab runner."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys
from typing import Iterable


_RECORDING = False


def _required_environment(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        raise SystemExit(f"friend-lab guard configuration missing: {name}")
    return value


def _load_root() -> tuple[Path, Path]:
    raw = Path(_required_environment("FRIEND_LAB_ROOT"))
    if not raw.is_absolute():
        raise SystemExit("friend-lab root must be absolute")
    if raw.is_symlink():
        raise SystemExit("friend-lab root must not be a symlink")
    try:
        resolved = raw.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise SystemExit("friend-lab root is not resolvable") from exc
    if not resolved.is_dir():
        raise SystemExit("friend-lab root must be an existing directory")
    return raw, resolved


def _has_symlink_below_root(root: Path, target: Path) -> bool:
    try:
        relative = target.relative_to(root)
    except ValueError:
        return True
    current = root
    for component in relative.parts[:-1]:
        current = current / component
        if current.is_symlink():
            return True
    return target.is_symlink()


def _load_ledger(raw_root: Path, resolved_root: Path) -> Path:
    raw = Path(_required_environment("FRIEND_LAB_LEDGER"))
    if not raw.is_absolute():
        raise SystemExit("friend-lab ledger must be absolute")
    if _has_symlink_below_root(raw_root, raw):
        raise SystemExit("friend-lab ledger path must not contain symlinks")
    try:
        parent = raw.parent.resolve(strict=True)
        resolved = parent / raw.name
        resolved.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit("friend-lab ledger must resolve beneath root") from exc
    if raw.exists() and not raw.is_file():
        raise SystemExit("friend-lab ledger must be a regular file")
    return resolved


def _load_phase() -> str:
    value = _required_environment("FRIEND_LAB_PHASE")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,95}", value):
        raise SystemExit("friend-lab phase is invalid")
    return value


_RAW_ROOT, _ROOT = _load_root()
_LEDGER = _load_ledger(_RAW_ROOT, _ROOT)
_PHASE = _load_phase()


def _record(operation_class: str) -> None:
    global _RECORDING
    if _RECORDING:
        return
    _RECORDING = True
    try:
        with _LEDGER.open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "phase": _PHASE,
                        "operation_class": operation_class,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )
    finally:
        _RECORDING = False


def _open_is_write(args: tuple[object, ...]) -> bool:
    mode = args[1] if len(args) > 1 else None
    flags = args[2] if len(args) > 2 else None
    if isinstance(mode, str) and any(item in mode for item in "wax+"):
        return True
    if isinstance(flags, int):
        write_flags = (
            os.O_WRONLY
            | os.O_RDWR
            | os.O_APPEND
            | os.O_CREAT
            | os.O_TRUNC
        )
        return bool(flags & write_flags)
    return False


def _dir_fd(args: tuple[object, ...], index: int) -> int | None:
    if len(args) <= index or args[index] in {None, -1}:
        return None
    value = args[index]
    return value if isinstance(value, int) and not isinstance(value, bool) else -2


def _write_paths(
    event: str, args: tuple[object, ...]
) -> tuple[tuple[object, int | None], ...]:
    if event == "open":
        return ((args[0], None),) if args and _open_is_write(args) else ()
    if event in {"os.rename", "os.replace", "os.link"}:
        return (
            (args[0], _dir_fd(args, 2)),
            (args[1], _dir_fd(args, 3)),
        )
    if event in {"os.symlink", "shutil.copyfile", "shutil.copymode", "shutil.copystat"}:
        directory_fd = _dir_fd(args, 2) if event == "os.symlink" else None
        return ((args[1], directory_fd),) if len(args) > 1 else ((None, None),)
    if event in {
        "os.remove",
        "os.unlink",
        "os.rmdir",
        "os.truncate",
        "shutil.rmtree",
    }:
        directory_fd = _dir_fd(args, 1) if event.startswith("os.") else None
        return ((args[0], directory_fd),) if args else ((None, None),)
    if event == "os.mkdir":
        return ((args[0], _dir_fd(args, 2)),) if args else ((None, None),)
    if event == "os.chmod":
        return ((args[0], _dir_fd(args, 2)),) if args else ((None, None),)
    if event == "os.chown":
        return ((args[0], _dir_fd(args, 3)),) if args else ((None, None),)
    if event == "os.utime":
        return ((args[0], _dir_fd(args, 3)),) if args else ((None, None),)
    return ()


def _directory_for_fd(directory_fd: int | None) -> Path | None:
    if directory_fd is None:
        return Path.cwd()
    if directory_fd < 0:
        return None
    for prefix in (Path("/dev/fd"), Path("/proc/self/fd")):
        candidate = prefix / str(directory_fd)
        try:
            resolved = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if resolved.is_dir():
            return resolved
    return None


def _resolve_event_path(
    value: object, directory_fd: int | None = None
) -> Path | None:
    if isinstance(value, int):
        return None
    try:
        raw = os.fspath(value)
    except (TypeError, ValueError):
        return None
    if isinstance(raw, bytes):
        raw = os.fsdecode(raw)
    if not isinstance(raw, str) or not raw or "\x00" in raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        directory = _directory_for_fd(directory_fd)
        if directory is None:
            return None
        path = directory / path
    try:
        if path.exists() or path.is_symlink():
            return path.resolve(strict=True)
        parent = path.parent.resolve(strict=True)
        return parent / path.name
    except (OSError, RuntimeError):
        return None


def _inside_root(value: object, directory_fd: int | None = None) -> bool:
    resolved = _resolve_event_path(value, directory_fd)
    if resolved is None:
        return False
    try:
        resolved.relative_to(_ROOT)
    except ValueError:
        return False
    return True


def _all_inside_root(paths: Iterable[tuple[object, int | None]]) -> bool:
    observed = tuple(paths)
    return bool(observed) and all(
        _inside_root(item, directory_fd) for item, directory_fd in observed
    )


_ORIGINAL_OS_OPEN = os.open


def _guarded_os_open(
    path: object,
    flags: int,
    mode: int = 0o777,
    *,
    dir_fd: int | None = None,
) -> int:
    write_args = (path, None, flags)
    if dir_fd is not None and _open_is_write(write_args):
        resolved = _resolve_event_path(path, dir_fd)
        if resolved is None or not _inside_root(resolved):
            _record("outside-write")
            raise PermissionError("friend-lab outside write blocked")
        return _ORIGINAL_OS_OPEN(resolved, flags, mode)
    return _ORIGINAL_OS_OPEN(path, flags, mode, dir_fd=dir_fd)


def _audit(event: str, args: tuple[object, ...]) -> None:
    if _RECORDING:
        return
    if event.startswith("socket."):
        _record("socket")
        raise PermissionError("friend-lab socket operation blocked")
    paths = _write_paths(event, args)
    if paths and not _all_inside_root(paths):
        _record("outside-write")
        raise PermissionError("friend-lab outside write blocked")


sys.addaudithook(_audit)
os.open = _guarded_os_open
