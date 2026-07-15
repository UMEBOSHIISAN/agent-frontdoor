"""Mechanical proof that the preflight package has no execution path."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path
import re

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
        "popen",
        "system",
        "startfile",
    }
)
FORBIDDEN_CALLS = frozenset(
    {
        "eval",
        "exec",
        "os.popen",
        "os.system",
        "os.startfile",
        "runpy.run_module",
        "runpy.run_path",
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
    r"(?:^|\.)(?:call|dispatch|execute|invoke|launch|run|spawn|start)_?"
    r"(?:local_)?worker$"
)
ALLOWED_STREAM_WRITES = frozenset({"sys.stdout.write", "sys.stderr.write"})


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def _literal_open_mode(call: ast.Call, name: str) -> str | None:
    for keyword in call.keywords:
        if keyword.arg == "mode":
            return keyword.value.value if isinstance(
                keyword.value, ast.Constant
            ) and isinstance(keyword.value.value, str) else "<dynamic>"

    position = 1 if name == "open" else 0
    if len(call.args) <= position:
        return None
    value = call.args[position]
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return "<dynamic>"


def _stream_target(call: ast.Call) -> str | None:
    if len(call.args) >= 2:
        return _dotted_name(call.args[1])
    for keyword in call.keywords:
        if keyword.arg in {"fp", "stream"}:
            return _dotted_name(keyword.value)
    return None


def _source_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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
        name = _dotted_name(node.func)
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
                    f"line {node.lineno}: non-read open mode {mode!r}"
                )

        if name in {"json.dump", "yaml.dump"}:
            target = _stream_target(node)
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
