#!/usr/bin/env python3
"""Positive control: attempt one write outside the friend-lab root."""

from __future__ import annotations

import os
from pathlib import Path


def main() -> int:
    target = os.environ.get("FRIEND_LAB_CONTROL_OUTSIDE")
    if target is None or target == "":
        raise SystemExit("FRIEND_LAB_CONTROL_OUTSIDE is required")
    Path(target).write_text("synthetic control\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
