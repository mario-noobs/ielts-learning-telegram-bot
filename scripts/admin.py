#!/usr/bin/env python3
"""Admin CLI — first-admin bootstrap + plan assignment (US-M11.2).

The chicken-and-egg problem: the admin UI gates on
``role == 'platform_admin'`` but no user has that role until someone
sets it manually. This CLI is that someone.

All commands address users by their **Firebase auth_uid** (the
identity already in their session token); the CLI resolves uid →
``users.id`` via the UNIQUE ``auth_uid`` column added in M8.1.

Every mutation lands an ``audit_log`` row through
``services.admin.audit_service.log_event`` so the action trail
is complete from day one.

Examples:
    python scripts/admin.py grant-admin --uid 7Hk...XYZ
    python scripts/admin.py revoke-admin --uid 7Hk...XYZ
    python scripts/admin.py set-plan --uid 7Hk...XYZ --plan personal_pro \
        --expires 2027-01-01
    python scripts/admin.py list-admins
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import date
from pathlib import Path

# Project root on sys.path so this is runnable as `python scripts/admin.py`.
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy import select, update  # noqa: E402

from services.admin import audit_service  # noqa: E402
from services.db import get_sync_session  # noqa: E402
from services.db.models import User  # noqa: E402

VALID_ROLES = ("user", "team_admin", "org_admin", "platform_admin")


def _actor() -> str:
    """Return a human-meaningful actor id for the audit row."""
    return f"cli:{getpass.getuser()}"


def _user_by_auth_uid(auth_uid: str) -> User | None:
    with get_sync_session() as s:
        return s.execute(
            select(User).where(User.auth_uid == auth_uid),
        ).scalar_one_or_none()


def _print(payload: dict | list) -> None:
    print(json.dumps(payload, indent=2, default=str))


# ─── grant-admin ─────────────────────────────────────────────────────


def _cmd_grant_admin(args: argparse.Namespace) -> int:
    user = _user_by_auth_uid(args.uid)
    if user is None:
        print(f"error: no user with auth_uid={args.uid!r}", file=sys.stderr)
        return 1
    before = {"role": user.role}
    if user.role == "platform_admin":
        print(f"already platform_admin: id={user.id} auth_uid={args.uid}")
        return 0

    with get_sync_session() as s, s.begin():
        s.execute(
            update(User).where(User.id == user.id).values(role="platform_admin"),
        )

    audit_service.log_event(
        actor_uid=_actor(),
        event_type="user.role_granted",
        target_kind="user",
        target_id=user.id,
        before=before,
        after={"role": "platform_admin"},
    )
    print(f"granted platform_admin: id={user.id} auth_uid={args.uid}")
    return 0


# ─── revoke-admin ────────────────────────────────────────────────────


def _cmd_revoke_admin(args: argparse.Namespace) -> int:
    user = _user_by_auth_uid(args.uid)
    if user is None:
        print(f"error: no user with auth_uid={args.uid!r}", file=sys.stderr)
        return 1
    before = {"role": user.role}
    if user.role == "user":
        print(f"already plain user: id={user.id} auth_uid={args.uid}")
        return 0

    with get_sync_session() as s, s.begin():
        s.execute(update(User).where(User.id == user.id).values(role="user"))

    audit_service.log_event(
        actor_uid=_actor(),
        event_type="user.role_revoked",
        target_kind="user",
        target_id=user.id,
        before=before,
        after={"role": "user"},
    )
    print(f"revoked role -> user: id={user.id} auth_uid={args.uid}")
    return 0


# ─── set-plan ────────────────────────────────────────────────────────


def _cmd_set_plan(args: argparse.Namespace) -> int:
    user = _user_by_auth_uid(args.uid)
    if user is None:
        print(f"error: no user with auth_uid={args.uid!r}", file=sys.stderr)
        return 1

    expires: date | None = None
    if args.expires:
        try:
            expires = date.fromisoformat(args.expires)
        except ValueError:
            print(f"error: --expires must be YYYY-MM-DD, got {args.expires!r}",
                  file=sys.stderr)
            return 1

    before = {"plan": user.plan, "plan_expires_at": user.plan_expires_at}
    try:
        with get_sync_session() as s, s.begin():
            s.execute(
                update(User)
                .where(User.id == user.id)
                .values(plan=args.plan, plan_expires_at=expires),
            )
    except Exception as exc:
        # FK violation if --plan isn't in plans.id
        print(f"error: {exc}", file=sys.stderr)
        return 1

    audit_service.log_event(
        actor_uid=_actor(),
        event_type="user.plan_assigned",
        target_kind="user",
        target_id=user.id,
        before=before,
        after={"plan": args.plan, "plan_expires_at": expires},
    )
    print(
        f"plan -> {args.plan}"
        + (f" (expires {expires})" if expires else "")
        + f": id={user.id} auth_uid={args.uid}",
    )
    return 0


# ─── list-admins ─────────────────────────────────────────────────────


def _cmd_list_admins(_args: argparse.Namespace) -> int:
    with get_sync_session() as s:
        rows = (
            s.execute(select(User).where(User.role != "user").order_by(User.id))
            .scalars()
            .all()
        )
    _print(
        [
            {
                "id": u.id,
                "auth_uid": u.auth_uid,
                "name": u.name,
                "email": u.email,
                "role": u.role,
                "plan": u.plan,
                "plan_expires_at": u.plan_expires_at,
            }
            for u in rows
        ],
    )
    return 0


# ─── argparse wiring ─────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="admin", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("grant-admin", help="Set role=platform_admin for a user.")
    g.add_argument("--uid", required=True, help="Firebase auth_uid.")
    g.set_defaults(func=_cmd_grant_admin)

    r = sub.add_parser("revoke-admin", help="Reset role=user for a user.")
    r.add_argument("--uid", required=True, help="Firebase auth_uid.")
    r.set_defaults(func=_cmd_revoke_admin)

    sp = sub.add_parser("set-plan", help="Assign a plan to a user.")
    sp.add_argument("--uid", required=True, help="Firebase auth_uid.")
    sp.add_argument("--plan", required=True, help="Plan id (e.g. personal_pro).")
    sp.add_argument("--expires", help="Optional YYYY-MM-DD expiry date.")
    sp.set_defaults(func=_cmd_set_plan)

    la = sub.add_parser("list-admins", help="Print every user with role != 'user'.")
    la.set_defaults(func=_cmd_list_admins)

    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
