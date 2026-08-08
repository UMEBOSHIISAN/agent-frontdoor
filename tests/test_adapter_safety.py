"""Mechanical safety boundary for the optional runtime adapter."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "adapters" / "src" / "frontdoor_hooks"

FORBIDDEN_IMPORTS = frozenset(
    {
        "aiohttp",
        "anthropic",
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
FORBIDDEN_CALLS = frozenset(
    {
        "eval",
        "exec",
        "os.popen",
        "os.system",
        "runpy.run_module",
        "runpy.run_path",
        "time.sleep",
    }
)
FORBIDDEN_PREFIXES = (
    "aiohttp.",
    "anthropic.",
    "httpx.",
    "litellm.",
    "ollama.",
    "openai.",
    "paramiko.",
    "requests.",
    "socket.",
    "subprocess.",
    "urllib.request.",
)


def _name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return None


def _violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] in FORBIDDEN_IMPORTS:
                    violations.append(f"forbidden import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.split(".", 1)[0] in FORBIDDEN_IMPORTS:
                violations.append(f"forbidden import from {module}")
        elif isinstance(node, ast.Call):
            name = _name(node.func)
            if name in FORBIDDEN_CALLS or (
                name is not None
                and any(name.startswith(prefix) for prefix in FORBIDDEN_PREFIXES)
            ):
                violations.append(f"forbidden call {name}")
    return violations


def test_adapter_has_no_network_command_worker_or_retry_execution_path() -> None:
    paths = sorted(SOURCE.rglob("*.py"))
    assert paths

    failures = {
        str(path.relative_to(ROOT)): _violations(path)
        for path in paths
        if _violations(path)
    }

    assert not failures


def test_safety_guard_detects_forbidden_adapter_examples(tmp_path: Path) -> None:
    cases = {
        "network.py": "import socket\nsocket.create_connection(('x', 1))",
        "command.py": "import subprocess\nsubprocess.run(['worker'])",
        "retry.py": "import time\ntime.sleep(1)",
    }
    for name, source in cases.items():
        path = tmp_path / name
        path.write_text(source, encoding="utf-8")
        assert _violations(path), name
