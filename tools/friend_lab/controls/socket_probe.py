#!/usr/bin/env python3
"""Positive control: attempt one socket construction."""

from __future__ import annotations

import socket


def main() -> int:
    probe = socket.socket()
    probe.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
