#!/usr/bin/env python3
"""Feature flag admin CLI.

Examples:
    python scripts/flags.py list
    python scripts/flags.py get design_system_v2
    python scripts/flags.py set design_system_v2 --enabled --pct=10 \
        --allowlist=uid1,uid2 --desc="Route web to new design"
    python scripts/flags.py delete design_system_v2

Requires the same Firebase credentials the bot uses (see config.py).
All Firestore access goes through services.feature_flag_service — this
script MUST NOT duplicate Firestore logic.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path when this file is run directly.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from services import feature_flag_service as ffs  # noqa: E402


def _flag_to_printable(flag: Optional[ffs.FeatureFlag]) -> dict:
    if flag is None:
        return {}
    d = flag.to_dict()
    # Firestore timestamps are not JSON-serializable — coerce.
    ua = d.get("updated_at")
    if ua is not None and not isinstance(ua, str):
        d["updated_at"] = str(ua)
    return d


def cmd_list(_args: argparse.Namespace) -> int:
    flags = ffs.list_flags()
    if not flags:
        print("(no flags defined)")
        return 0
    print(json.dumps([_flag_to_printable(f) for f in flags], indent=2))
    return 0


def cmd_get(args: argparse.Namespace) -> int:
    flag = ffs.get_flag(args.name)
    if flag is None:
        print(f"flag not found: {args.name}", file=sys.stderr)
        return 1
    print(json.dumps(_flag_to_printable(flag), indent=2))
    return 0


def cmd_set(args: argparse.Namespace) -> int:
    allowlist = [u.strip() for u in (args.allowlist or "").split(",") if u.strip()]
    flag = ffs.set_flag(
        args.name,
        enabled=bool(args.enabled),
        rollout_pct=int(args.pct),
        uid_allowlist=allowlist,
        description=args.desc or "",
    )
    print(json.dumps(_flag_to_printable(flag), indent=2))
    return 0


def cmd_delete(args: argparse.Namespace) -> int:
    ffs.delete_flag(args.name)
    print(f"deleted {args.name}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Feature flag admin CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list all flags")
    p_list.set_defaults(func=cmd_list)

    p_get = sub.add_parser("get", help="print one flag")
    p_get.add_argument("name")
    p_get.set_defaults(func=cmd_get)

    p_set = sub.add_parser("set", help="upsert a flag")
    p_set.add_argument("name")
    p_set.add_argument("--enabled", action="store_true", help="turn the flag on")
    p_set.add_argument(
        "--pct",
        type=int,
        default=0,
        help="rollout percentage 0-100 (clamped)",
    )
    p_set.add_argument(
        "--allowlist",
        default="",
        help="comma-separated Firebase Auth UIDs always on",
    )
    p_set.add_argument("--desc", default="", help="free-text description")
    p_set.set_defaults(func=cmd_set)

    p_del = sub.add_parser("delete", help="delete a flag")
    p_del.add_argument("name")
    p_del.set_defaults(func=cmd_delete)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
