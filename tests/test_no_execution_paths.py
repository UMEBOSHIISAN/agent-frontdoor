"""Mechanical proof that the preflight package has no execution path."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re

import pytest

from frontdoor.cli import build_parser


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "frontdoor"

FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "aiohttp",
        "anthropic",
        "ftplib",
        "http",
        "httpx",
        "litellm",
        "multiprocessing",
        "ollama",
        "openai",
        "paramiko",
        "pty",
        "requests",
        "socket",
        "subprocess",
        "telnetlib",
        "transformers",
        "urllib",
        "urllib3",
    }
)
FORBIDDEN_OS_NAMES = frozenset(
    {
        "makedirs",
        "popen",
        "system",
        "startfile",
    }
)
FORBIDDEN_CALLS = frozenset(
    {
        "__import__",
        "builtins.__import__",
        "eval",
        "exec",
        "importlib.import_module",
        "os.makedirs",
        "os.popen",
        "os.system",
        "os.startfile",
        "runpy.run_module",
        "runpy.run_path",
        "shutil.rmtree",
    }
)
FORBIDDEN_CALL_PREFIXES = (
    "aiohttp.",
    "anthropic.",
    "asyncio.create_subprocess_",
    "ftplib.",
    "http.client.",
    "httpx.",
    "litellm.",
    "ollama.",
    "openai.",
    "os.exec",
    "os.spawn",
    "paramiko.",
    "pty.spawn",
    "requests.",
    "socket.",
    "subprocess.",
    "telnetlib.",
    "urllib.request.",
    "urllib3.",
)
WRITE_METHODS = frozenset(
    {
        "hardlink_to",
        "mkdir",
        "rename",
        "replace",
        "rmdir",
        "symlink_to",
        "touch",
        "unlink",
        "write_bytes",
        "write_text",
    }
)
WORKER_LAUNCHER = re.compile(
    r"(?:^|\.)(?:(?:call|dispatch|execute|invoke|launch|run|spawn|start)_?"
    r"(?:local_)?worker|(?:local_)?workers?\."
    r"(?:call|dispatch|execute|invoke|launch|run|spawn|start))$"
)
ALLOWED_STREAM_WRITES = frozenset({"sys.stdout.write", "sys.stderr.write"})


def _import_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local_name = alias.asname or alias.name.split(".", 1)[0]
                canonical_name = (
                    alias.name if alias.asname else alias.name.split(".", 1)[0]
                )
                aliases[local_name] = canonical_name
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                if alias.name == "*":
                    continue
                local_name = alias.asname or alias.name
                canonical_name = (
                    f"{module}.{alias.name}" if module else alias.name
                )
                aliases[local_name] = canonical_name
    return aliases


def _dotted_name(
    node: ast.AST, aliases: dict[str, str] | None = None
) -> str | None:
    if isinstance(node, ast.Name):
        return (aliases or {}).get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value, aliases)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def _literal_open_mode(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == "mode":
            return keyword.value.value if isinstance(
                keyword.value, ast.Constant
            ) and isinstance(keyword.value.value, str) else "<dynamic>"

    position = 1 if name in {"open", "builtins.open", "io.open"} else 0
    if len(call.args) <= position:
        return None
    value = call.args[position]
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return "<dynamic>"


def _stream_target(
    call: ast.Call, aliases: dict[str, str]
) -> str | None:
    if len(call.args) >= 2:
        return _dotted_name(call.args[1], aliases)
    for keyword in call.keywords:
        if keyword.arg in {"fp", "stream"}:
            return _dotted_name(keyword.value, aliases)
    return None


def _source_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    aliases = _import_aliases(tree)
    violations: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS:
                    violations.append(
                        f"line {node.lineno}: forbidden import {alias.name}"
                    )

        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".", 1)[0] in FORBIDDEN_IMPORT_ROOTS:
                violations.append(
                    f"line {node.lineno}: forbidden import from {module}"
                )
            if module == "os":
                for alias in node.names:
                    if alias.name in FORBIDDEN_OS_NAMES or alias.name.startswith(
                        ("exec", "spawn")
                    ):
                        violations.append(
                            f"line {node.lineno}: forbidden os import "
                            f"{alias.name}"
                        )

        if not isinstance(node, ast.Call):
            continue
        name = _dotted_name(node.func, aliases)
        if not name:
            continue
        if name in FORBIDDEN_CALLS or any(
            name.startswith(prefix) for prefix in FORBIDDEN_CALL_PREFIXES
        ):
            violations.append(f"line {node.lineno}: forbidden call {name}")
        if WORKER_LAUNCHER.search(name):
            violations.append(
                f"line {node.lineno}: forbidden worker launcher {name}"
            )

        leaf = name.rsplit(".", 1)[-1]
        if leaf in WRITE_METHODS:
            violations.append(f"line {node.lineno}: file mutation call {name}")
        if leaf in {"write", "writelines"} and name not in ALLOWED_STREAM_WRITES:
            violations.append(f"line {node.lineno}: file write call {name}")

        if name == "open" or name.endswith(".open"):
            mode = _literal_open_mode(node, name)
            if mode == "<dynamic>" or (
                mode is not None and any(flag in mode for flag in "wax+")
            ):
                violations.append(
                    f"line {node.lineno}: non-read open mode {mode!r} via {name}"
                )

        if name in {"json.dump", "yaml.dump"}:
            target = _stream_target(node, aliases)
            if target not in {"sys.stdout", "sys.stderr"}:
                violations.append(
                    f"line {node.lineno}: serialization write via {name}"
                )

    return violations


def test_frontdoor_source_has_no_execution_network_or_write_path() -> None:
    paths = sorted(SOURCE.rglob("*.py"))
    assert paths, f"no Python source found under {SOURCE.relative_to(ROOT)}"

    failures = {}
    for path in paths:
        violations = _source_violations(path)
        if violations:
            failures[str(path.relative_to(ROOT))] = violations
    assert not failures, f"forbidden source paths: {failures}"


def test_cli_exposes_only_the_four_read_only_preflight_commands() -> None:
    parser = build_parser()
    subparsers = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    assert len(subparsers) == 1

    command_names = set(subparsers[0].choices)
    assert command_names == {"validate", "card", "explain", "check-drift"}
    assert command_names.isdisjoint(
        {
            "call-worker",
            "delete",
            "deploy",
            "dispatch",
            "execute",
            "install",
            "invoke",
            "launch",
            "publish",
            "route",
            "run",
            "start",
        }
    )


@pytest.mark.parametrize(
    ("source", "expected_name"),
    [
        ("import os as o\no.system('command')", "os.system"),
        ("from os import system as s\ns('command')", "os.system"),
        ("import os as o\no.makedirs('output')", "os.makedirs"),
        ("from os import makedirs as md\nmd('output')", "os.makedirs"),
        ("import shutil as sh\nsh.rmtree('output')", "shutil.rmtree"),
        (
            "from shutil import rmtree as remove_tree\n"
            "remove_tree('output')",
            "shutil.rmtree",
        ),
        ("import io\nio.open('output.json', 'w')", "io.open"),
        (
            "from io import open as io_open\n"
            "io_open('output.json', mode='w')",
            "io.open",
        ),
        ("__import__('socket')", "__import__"),
        (
            "import importlib as il\nil.import_module('requests')",
            "importlib.import_module",
        ),
        (
            "from importlib import import_module as load\nload('socket')",
            "importlib.import_module",
        ),
        ("import subprocess as sp\nsp.run(['worker'])", "subprocess.run"),
        (
            "from socket import create_connection as connect\n"
            "connect(('example.invalid', 443))",
            "socket.create_connection",
        ),
        (
            "from local_worker import invoke as go\ngo()",
            "local_worker.invoke",
        ),
    ],
)
def test_guard_self_rejects_forbidden_source_through_aliases(
    tmp_path: Path, source: str, expected_name: str
) -> None:
    path = tmp_path / "forbidden_sample.py"
    path.write_text(source, encoding="utf-8")

    violations = _source_violations(path)

    assert any(expected_name in violation for violation in violations), violations


@pytest.mark.parametrize(
    "source",
    [
        "from pathlib import Path\nPath('schema.json').read_text()",
        "open('task.json', 'r', encoding='utf-8')",
        "import io\nio.open('task.json', 'r', encoding='utf-8')",
        "import sys\nsys.stdout.write('ok')\nsys.stderr.write('note')",
        "import sys\nprint('note', file=sys.stderr)",
    ],
)
def test_guard_self_allows_local_reads_and_standard_streams(
    tmp_path: Path, source: str
) -> None:
    path = tmp_path / "safe_sample.py"
    path.write_text(source, encoding="utf-8")

    assert _source_violations(path) == []
