#!/usr/bin/env python3
"""CLI entry for SmartCAT.AI."""
from __future__ import annotations

import sys

from main import build_parser, run_pipeline


def main() -> int:
    parser = build_parser()
    ns = parser.parse_args()
    if not any([ns.module1, ns.module2, ns.module3, ns.module4, ns.module5, ns.module6]):
        parser.error("Select at least one --moduleN flag")
    run_pipeline(ns)
    return 0


if __name__ == "__main__":
    sys.exit(main())
