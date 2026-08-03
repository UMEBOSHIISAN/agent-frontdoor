from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
GUARD_DIR = ROOT / "tools" / "friend_lab"
WRITE_PROBE = GUARD_DIR / "controls" / "write_outside_probe.py"
SOCKET_PROBE = GUARD_DIR / "controls" / "socket_probe.py"


def guarded_environment(
    root: Path,
    ledger: Path,
    phase: str,
    **extra: str,
) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "PYTHONPATH": str(GUARD_DIR),
            "PYTHONDONTWRITEBYTECODE": "1",
            "FRIEND_LAB_ROOT": str(root),
            "FRIEND_LAB_LEDGER": str(ledger),
            "FRIEND_LAB_PHASE": phase,
            **extra,
        }
    )
    return env


def records(ledger: Path) -> list[dict[str, object]]:
    if not ledger.exists():
        return []
    return [
        json.loads(line)
        for line in ledger.read_text(encoding="utf-8").splitlines()
        if line
    ]


def run_guarded_script(
    tmp_path: Path,
    phase: str,
    script: Path,
) -> tuple[subprocess.CompletedProcess[str], list[dict[str, object]]]:
    root = tmp_path / "lab-root"
    root.mkdir()
    ledger = root / "audit.jsonl"
    outside = tmp_path / "outside.txt"
    result = subprocess.run(
        [sys.executable, str(script)],
        env=guarded_environment(
            root,
            ledger,
            phase,
            FRIEND_LAB_CONTROL_OUTSIDE=str(outside),
        ),
        text=True,
        capture_output=True,
        check=False,
    )
    return result, records(ledger)


def run_guarded_code(
    root: Path,
    ledger: Path,
    phase: str,
    code: str,
    **extra: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        env=guarded_environment(root, ledger, phase, **extra),
        text=True,
        capture_output=True,
        check=False,
    )


def test_socket_probe_is_blocked_and_sanitized(tmp_path: Path) -> None:
    result, ledger_records = run_guarded_script(
        tmp_path, "socket-control", SOCKET_PROBE
    )

    assert result.returncode != 0
    assert ledger_records == [
        {"phase": "socket-control", "operation_class": "socket"}
    ]


def test_outside_write_probe_is_blocked_and_sanitized(tmp_path: Path) -> None:
    result, ledger_records = run_guarded_script(
        tmp_path, "write-control", WRITE_PROBE
    )

    assert result.returncode != 0
    assert ledger_records == [
        {"phase": "write-control", "operation_class": "outside-write"}
    ]
    assert not (tmp_path / "outside.txt").exists()


def test_inside_root_write_is_allowed_without_ledger_event(
    tmp_path: Path,
) -> None:
    root = tmp_path / "lab-root"
    root.mkdir()
    ledger = root / "audit.jsonl"
    inside = root / "allowed.txt"
    result = run_guarded_code(
        root,
        ledger,
        "inside-write",
        "from pathlib import Path; import os; "
        "Path(os.environ['INSIDE']).write_text('allowed', encoding='utf-8')",
        INSIDE=str(inside),
    )

    assert result.returncode == 0, result.stderr
    assert inside.read_text(encoding="utf-8") == "allowed"
    assert records(ledger) == []


def test_read_outside_root_is_allowed(tmp_path: Path) -> None:
    root = tmp_path / "lab-root"
    root.mkdir()
    ledger = root / "audit.jsonl"
    outside = tmp_path / "read-only.txt"
    outside.write_text("public", encoding="utf-8")
    result = run_guarded_code(
        root,
        ledger,
        "outside-read",
        "from pathlib import Path; import os; "
        "assert Path(os.environ['OUTSIDE']).read_text() == 'public'",
        OUTSIDE=str(outside),
    )

    assert result.returncode == 0, result.stderr
    assert records(ledger) == []


def test_relative_root_fails_visibly(tmp_path: Path) -> None:
    ledger = tmp_path / "audit.jsonl"
    result = run_guarded_code(
        Path("relative-root"),
        ledger,
        "invalid-root",
        "print('must not run')",
    )

    assert result.returncode != 0
    assert "must not run" not in result.stdout
    assert records(ledger) == []


def test_symlink_root_fails_visibly(tmp_path: Path) -> None:
    real_root = tmp_path / "real-root"
    real_root.mkdir()
    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(real_root, target_is_directory=True)
    ledger = real_root / "audit.jsonl"
    result = run_guarded_code(
        linked_root,
        ledger,
        "invalid-root",
        "print('must not run')",
    )

    assert result.returncode != 0
    assert "must not run" not in result.stdout
    assert records(ledger) == []


def test_ledger_outside_root_fails_visibly(tmp_path: Path) -> None:
    root = tmp_path / "lab-root"
    root.mkdir()
    ledger = tmp_path / "outside-ledger.jsonl"
    result = run_guarded_code(
        root,
        ledger,
        "invalid-ledger",
        "print('must not run')",
    )

    assert result.returncode != 0
    assert "must not run" not in result.stdout
    assert records(ledger) == []


def test_symlink_ledger_ancestor_fails_visibly(tmp_path: Path) -> None:
    root = tmp_path / "lab-root"
    root.mkdir()
    real_parent = root / "real-ledger-parent"
    real_parent.mkdir()
    linked_parent = root / "linked-ledger-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    ledger = linked_parent / "audit.jsonl"
    result = run_guarded_code(
        root,
        ledger,
        "invalid-ledger",
        "print('must not run')",
    )

    assert result.returncode != 0
    assert "must not run" not in result.stdout
    assert records(real_parent / "audit.jsonl") == []


def test_missing_required_environment_fails_visibly(tmp_path: Path) -> None:
    root = tmp_path / "lab-root"
    root.mkdir()
    ledger = root / "audit.jsonl"
    env = guarded_environment(root, ledger, "missing-env")
    del env["FRIEND_LAB_PHASE"]
    result = subprocess.run(
        [sys.executable, "-c", "print('must not run')"],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "must not run" not in result.stdout
    assert records(ledger) == []


def test_unresolved_file_descriptor_write_is_denied_and_recorded(
    tmp_path: Path,
) -> None:
    root = tmp_path / "lab-root"
    root.mkdir()
    ledger = root / "audit.jsonl"
    result = run_guarded_code(
        root,
        ledger,
        "unresolved-write",
        "open(987654321, 'w')",
    )

    assert result.returncode != 0
    assert records(ledger) == [
        {"phase": "unresolved-write", "operation_class": "outside-write"}
    ]


def test_rename_from_inside_to_outside_is_denied_and_recorded(
    tmp_path: Path,
) -> None:
    root = tmp_path / "lab-root"
    root.mkdir()
    ledger = root / "audit.jsonl"
    source = root / "source.txt"
    source.write_text("keep", encoding="utf-8")
    destination = tmp_path / "destination.txt"
    result = run_guarded_code(
        root,
        ledger,
        "rename-outside",
        "import os; os.rename(os.environ['SOURCE'], os.environ['DESTINATION'])",
        SOURCE=str(source),
        DESTINATION=str(destination),
    )

    assert result.returncode != 0
    assert source.exists()
    assert not destination.exists()
    assert records(ledger) == [
        {"phase": "rename-outside", "operation_class": "outside-write"}
    ]


def test_dir_fd_cannot_redirect_relative_write_outside_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "lab-root"
    root.mkdir()
    ledger = root / "audit.jsonl"
    outside_directory = tmp_path / "outside-directory"
    outside_directory.mkdir()
    escaped = outside_directory / "escaped.txt"
    result = run_guarded_code(
        root,
        ledger,
        "dir-fd-outside-write",
        "import os; "
        "os.chdir(os.environ['FRIEND_LAB_ROOT']); "
        "directory_fd = os.open(os.environ['OUTSIDE_DIRECTORY'], os.O_RDONLY); "
        "file_fd = os.open('escaped.txt', os.O_WRONLY | os.O_CREAT, 0o600, "
        "dir_fd=directory_fd); "
        "os.close(file_fd); os.close(directory_fd)",
        OUTSIDE_DIRECTORY=str(outside_directory),
    )

    assert result.returncode != 0
    assert not escaped.exists()
    assert records(ledger) == [
        {"phase": "dir-fd-outside-write", "operation_class": "outside-write"}
    ]


def test_ledger_records_have_exact_closed_fields(tmp_path: Path) -> None:
    result, ledger_records = run_guarded_script(
        tmp_path, "sanitized-control", WRITE_PROBE
    )

    assert result.returncode != 0
    assert len(ledger_records) == 1
    assert set(ledger_records[0]) == {"phase", "operation_class"}
    serialized = json.dumps(ledger_records[0], sort_keys=True)
    for forbidden in (
        "path",
        "target",
        "content",
        "hostname",
        "environment",
    ):
        assert forbidden not in serialized
