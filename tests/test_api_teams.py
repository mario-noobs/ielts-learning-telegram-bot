"""Integration tests for self-serve team workspace routes (US-#332-#335)."""

from __future__ import annotations

import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update

from api.auth import get_current_user
from api.errors import ERR
from api.main import create_app

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping team workspace integration tests",
)


@pytest.fixture(autouse=True)
def _clean():
    from services.db import get_sync_session
    from services.db.models import (
        AuditLog,
        ListeningHistory,
        QuizHistory,
        ReadingSession,
        Team,
        TeamInvite,
        TeamKnowledgePost,
        TeamMember,
        User,
        UserVocabulary,
        WritingHistory,
    )

    def _wipe():
        with get_sync_session() as s, s.begin():
            s.execute(update(User).values(team_id=None))
            s.execute(delete(AuditLog))
            s.execute(delete(ReadingSession).where(ReadingSession.user_id.like("team-test-%")))
            s.execute(delete(ListeningHistory).where(ListeningHistory.user_id.like("team-test-%")))
            s.execute(delete(QuizHistory).where(QuizHistory.user_id.like("team-test-%")))
            s.execute(delete(WritingHistory).where(WritingHistory.user_id.like("team-test-%")))
            s.execute(delete(TeamKnowledgePost).where(TeamKnowledgePost.author_uid.like("team-test-%")))
            s.execute(delete(UserVocabulary).where(UserVocabulary.user_id.like("team-test-%")))
            s.execute(delete(TeamInvite))
            s.execute(delete(TeamMember))
            s.execute(delete(Team))
            s.execute(delete(User).where(User.id.like("team-test-%")))

    _wipe()
    yield
    _wipe()


def _seed_user(user_id: str, **fields) -> None:
    from services.db import get_sync_session
    from services.db.models import User

    with get_sync_session() as s, s.begin():
        s.add(User(id=user_id, name=fields.pop("name", user_id), **fields))


def _client(user_id: str, team_id: str | None = None) -> TestClient:
    app = create_app()

    async def _fake_user() -> dict:
        return {
            "id": user_id,
            "name": user_id,
            "role": "user",
            "plan": "free",
            "team_id": team_id,
        }

    app.dependency_overrides[get_current_user] = _fake_user
    return TestClient(app)


def _create_team(owner_id: str = "team-test-owner") -> str:
    _seed_user(owner_id)
    with _client(owner_id) as c:
        r = c.post("/api/v1/teams", json={"name": "Study Squad"})
    assert r.status_code == 201
    return r.json()["team"]["id"]


def _create_invite(team_id: str, owner_id: str = "team-test-owner") -> str:
    with _client(owner_id) as c:
        r = c.post(f"/api/v1/teams/{team_id}/invites", json={"role": "member"})
    assert r.status_code == 201
    return r.json()["token"]


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def test_create_team_links_creator_and_member_row() -> None:
    from services.db import get_sync_session
    from services.db.models import TeamMember, User

    _seed_user("team-test-owner")
    with _client("team-test-owner") as c:
        r = c.post("/api/v1/teams", json={"name": "Study Squad"})

    assert r.status_code == 201
    body = r.json()["team"]
    assert body["name"] == "Study Squad"
    assert body["seat_limit"] == 5
    assert body["member_count"] == 1
    assert body["my_role"] == "owner"

    with get_sync_session() as s:
        user = s.get(User, "team-test-owner")
        member = s.get(
            TeamMember,
            {"team_id": body["id"], "user_uid": "team-test-owner"},
        )
    assert user.team_id == body["id"]
    assert member.role == "admin"


def test_create_team_blocks_existing_team_member() -> None:
    _create_team("team-test-owner")
    with _client("team-test-owner") as c:
        r = c.post("/api/v1/teams", json={"name": "Another"})

    assert r.status_code == 409
    assert r.json()["error"]["code"] == ERR.team_already_joined.code


def test_create_invite_returns_shareable_path() -> None:
    team_id = _create_team()
    with _client("team-test-owner") as c:
        r = c.post(f"/api/v1/teams/{team_id}/invites", json={"role": "member"})

    assert r.status_code == 201
    body = r.json()
    assert body["token"]
    assert body["invite_url"] == f"/team/invite/{body['token']}"
    assert body["expires_at"]


def test_non_admin_cannot_create_invite() -> None:
    from services.db import get_sync_session
    from services.db.models import TeamMember, User

    team_id = _create_team()
    _seed_user("team-test-member")
    with get_sync_session() as s, s.begin():
        s.add(
            TeamMember(
                team_id=team_id,
                user_uid="team-test-member",
                role="member",
                joined_at=datetime.now(timezone.utc),
            )
        )
        s.execute(
            update(User).where(User.id == "team-test-member").values(team_id=team_id),
        )

    with _client("team-test-member", team_id=team_id) as c:
        r = c.post(f"/api/v1/teams/{team_id}/invites", json={"role": "member"})

    assert r.status_code == 403


def test_preview_invite_returns_public_team_summary() -> None:
    team_id = _create_team()
    token = _create_invite(team_id)

    with TestClient(create_app()) as c:
        r = c.get(f"/api/v1/teams/invites/{token}")

    assert r.status_code == 200
    assert r.json()["team_name"] == "Study Squad"
    assert r.json()["member_count"] == 1
    assert r.json()["seat_limit"] == 5


def test_accept_invite_links_user_to_team() -> None:
    from services.db import get_sync_session
    from services.db.models import TeamMember, User

    team_id = _create_team()
    token = _create_invite(team_id)
    _seed_user("team-test-invited")

    with _client("team-test-invited") as c:
        r = c.post(f"/api/v1/teams/invites/{token}/accept")

    assert r.status_code == 200
    assert r.json()["team"]["id"] == team_id
    assert r.json()["team"]["my_role"] == "member"
    with get_sync_session() as s:
        user = s.get(User, "team-test-invited")
        member = s.get(
            TeamMember,
            {"team_id": team_id, "user_uid": "team-test-invited"},
        )
    assert user.team_id == team_id
    assert member.role == "member"


def test_accept_invite_blocks_full_team() -> None:
    from services.db import get_sync_session
    from services.db.models import Team

    team_id = _create_team()
    token = _create_invite(team_id)
    _seed_user("team-test-invited")
    with get_sync_session() as s, s.begin():
        team = s.get(Team, team_id)
        team.seat_limit = 1

    with _client("team-test-invited") as c:
        r = c.post(f"/api/v1/teams/invites/{token}/accept")

    assert r.status_code == 409
    assert r.json()["error"]["code"] == ERR.team_seat_limit_reached.code


def test_accept_invite_rejects_expired_token() -> None:
    from services.db import get_sync_session
    from services.db.models import TeamInvite

    team_id = _create_team()
    token = "expired-token"
    with get_sync_session() as s, s.begin():
        s.add(
            TeamInvite(
                team_id=team_id,
                token_hash=_hash_token(token),
                role="member",
                created_by="team-test-owner",
                created_at=datetime.now(timezone.utc) - timedelta(days=10),
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
                metadata_json={},
            )
        )
    _seed_user("team-test-invited")

    with _client("team-test-invited") as c:
        r = c.post(f"/api/v1/teams/invites/{token}/accept")

    assert r.status_code == 410
    assert r.json()["error"]["code"] == ERR.team_invite_expired.code


def test_owner_can_update_member_role_and_remove_member() -> None:
    from services.db import get_sync_session
    from services.db.models import AuditLog, TeamMember, User

    team_id = _create_team()
    _seed_user("team-test-member", email="member@example.test")
    with get_sync_session() as s, s.begin():
        s.add(
            TeamMember(
                team_id=team_id,
                user_uid="team-test-member",
                role="member",
                joined_at=datetime.now(timezone.utc),
            )
        )
        s.execute(
            update(User).where(User.id == "team-test-member").values(team_id=team_id),
        )

    with _client("team-test-owner", team_id=team_id) as c:
        members = c.get(f"/api/v1/teams/{team_id}/members")
        promoted = c.patch(
            f"/api/v1/teams/{team_id}/members/team-test-member",
            json={"role": "admin"},
        )
        removed = c.delete(f"/api/v1/teams/{team_id}/members/team-test-member")

    assert members.status_code == 200
    roles = {m["user_id"]: m["role"] for m in members.json()["members"]}
    assert roles["team-test-owner"] == "owner"
    assert roles["team-test-member"] == "member"
    assert promoted.status_code == 200
    assert promoted.json()["member"]["role"] == "admin"
    assert removed.status_code == 204

    with get_sync_session() as s:
        user = s.get(User, "team-test-member")
        membership = s.get(
            TeamMember,
            {"team_id": team_id, "user_uid": "team-test-member"},
        )
        events = s.execute(
            select(AuditLog.event_type).where(AuditLog.target_id == team_id),
        ).scalars().all()
    assert user.team_id is None
    assert membership is None
    assert "team.member_role_updated" in events
    assert "team.member_removed" in events


def test_admin_cannot_change_roles_or_remove_admin() -> None:
    from services.db import get_sync_session
    from services.db.models import TeamMember, User

    team_id = _create_team()
    _seed_user("team-test-admin")
    _seed_user("team-test-member")
    with get_sync_session() as s, s.begin():
        s.add_all([
            TeamMember(
                team_id=team_id,
                user_uid="team-test-admin",
                role="admin",
                joined_at=datetime.now(timezone.utc),
            ),
            TeamMember(
                team_id=team_id,
                user_uid="team-test-member",
                role="member",
                joined_at=datetime.now(timezone.utc),
            ),
        ])
        s.execute(
            update(User)
            .where(User.id.in_(["team-test-admin", "team-test-member"]))
            .values(team_id=team_id),
        )

    with _client("team-test-admin", team_id=team_id) as c:
        promote = c.patch(
            f"/api/v1/teams/{team_id}/members/team-test-member",
            json={"role": "admin"},
        )
        remove_admin = c.delete(f"/api/v1/teams/{team_id}/members/team-test-owner")
        remove_member = c.delete(f"/api/v1/teams/{team_id}/members/team-test-member")

    assert promote.status_code == 403
    assert remove_admin.status_code == 403
    assert remove_member.status_code == 204


def test_team_overview_aggregates_weekly_activity() -> None:
    from services.db import get_sync_session
    from services.db.models import (
        ListeningHistory,
        QuizHistory,
        ReadingSession,
        ReviewEvent,
        TeamMember,
        User,
        WritingHistory,
    )

    owner_id = f"team-test-overview-owner-{uuid.uuid4().hex}"
    member_id = f"team-test-overview-member-{uuid.uuid4().hex}"
    team_id = _create_team(owner_id)
    _seed_user(member_id)
    now = datetime.now(timezone.utc)
    with get_sync_session() as s, s.begin():
        s.add(
            TeamMember(
                team_id=team_id,
                user_uid=member_id,
                role="member",
                joined_at=now,
            )
        )
        s.execute(
            update(User).where(User.id == member_id).values(team_id=team_id),
        )
        s.add_all([
            WritingHistory(id=f"{owner_id}-writing", user_id=owner_id, created_at=now),
            ListeningHistory(
                id=f"{owner_id}-listening",
                user_id=owner_id,
                submitted=True,
                created_at=now,
            ),
            QuizHistory(
                id=f"{member_id}-quiz",
                user_id=member_id,
                quiz_type="fill_blank",
                is_correct=True,
                is_challenge=False,
                created_at=now,
            ),
            ReadingSession(
                id=f"{member_id}-reading",
                user_id=member_id,
                passage_id="p1",
                status="submitted",
                questions=[],
                answer_key=[],
                submitted_at=now,
                updated_at=now,
            ),
            ReviewEvent(
                user_id=member_id,
                user_vocab_id="word-1",
                result=5,
                source=1,
                srs_interval_before=14,
                srs_interval_after=35,
                created_at=now,
            ),
        ])

    with _client(owner_id, team_id=team_id) as c:
        r = c.get(f"/api/v1/teams/{team_id}/overview")

    assert r.status_code == 200
    body = r.json()
    assert body["weekly_active_members"] == 2
    assert body["quiz_count"] == 1
    assert body["words_reviewed"] == 1
    assert body["words_mastered"] == 1
    assert body["study_minutes"] == 45


def test_owner_sees_privacy_safe_member_progress() -> None:
    from services.db import get_sync_session
    from services.db.models import ReviewEvent, TeamMember, User

    owner_id = f"team-test-progress-owner-{uuid.uuid4().hex}"
    member_id = f"team-test-progress-member-{uuid.uuid4().hex}"
    team_id = _create_team(owner_id)
    _seed_user(
        member_id,
        last_active_date=datetime.now(timezone.utc).date(),
        streak=4,
    )
    now = datetime.now(timezone.utc)
    with get_sync_session() as s, s.begin():
        s.add(
            TeamMember(
                team_id=team_id,
                user_uid=member_id,
                role="member",
                joined_at=now,
            )
        )
        s.execute(update(User).where(User.id == member_id).values(team_id=team_id))
        s.add(
            ReviewEvent(
                user_id=member_id,
                user_vocab_id=f"{member_id}-word",
                result=5,
                source=1,
                srs_interval_before=7,
                srs_interval_after=14,
                created_at=now,
            )
        )

    with _client(owner_id, team_id=team_id) as c:
        r = c.get(f"/api/v1/teams/{team_id}/member-progress")

    assert r.status_code == 200
    member = next(row for row in r.json()["members"] if row["user_id"] == member_id)
    assert member["words_reviewed"] == 1
    assert member["weekly_minutes"] == 3
    assert member["current_streak"] == 4
    assert "writing_submissions" not in member
    assert "answers" not in member
    assert "practice_history" not in member


def test_regular_member_cannot_view_member_progress_rows() -> None:
    from services.db import get_sync_session
    from services.db.models import TeamMember, User

    team_id = _create_team()
    _seed_user("team-test-member")
    with get_sync_session() as s, s.begin():
        s.add(
            TeamMember(
                team_id=team_id,
                user_uid="team-test-member",
                role="member",
                joined_at=datetime.now(timezone.utc),
            )
        )
        s.execute(
            update(User).where(User.id == "team-test-member").values(team_id=team_id),
        )

    with _client("team-test-member", team_id=team_id) as c:
        r = c.get(f"/api/v1/teams/{team_id}/member-progress")

    assert r.status_code == 403


def test_team_workspace_view_is_audited_without_private_details() -> None:
    from services.db import get_sync_session
    from services.db.models import AuditLog

    team_id = _create_team()

    with _client("team-test-owner", team_id=team_id) as c:
        r = c.post(f"/api/v1/teams/{team_id}/views")

    assert r.status_code == 204
    with get_sync_session() as s:
        event = s.execute(
            select(AuditLog).where(
                AuditLog.target_id == team_id,
                AuditLog.event_type == "team.dashboard_viewed",
            ),
        ).scalar_one()

    assert event.actor_uid == "team-test-owner"
    assert event.after == {"role": "owner", "member_count": 1}
    assert event.before is None


def test_member_shares_personal_word_to_team_feed_privacy_safe() -> None:
    from services.db import get_sync_session
    from services.db.models import TeamMember, User, UserVocabulary

    team_id = _create_team()
    _seed_user("team-test-member")
    now = datetime.now(timezone.utc)
    with get_sync_session() as s, s.begin():
        s.add(
            TeamMember(
                team_id=team_id,
                user_uid="team-test-member",
                role="member",
                joined_at=now,
            )
        )
        s.execute(
            update(User).where(User.id == "team-test-member").values(team_id=team_id),
        )
        s.add(
            UserVocabulary(
                id="team-test-word-1",
                user_id="team-test-member",
                word="scalability",
                normalized_word="scalability",
                topic_id=1,
                definition_en="ability to be enlarged or increased",
                definition_vi="kha nang mo rong",
                ipa="skæləbɪlɪti",
                part_of_speech="noun",
                example_en="The platform needs scalability.",
                example_vi="Nen tang can kha nang mo rong.",
                user_note="private note",
                source=3,
                srs_interval=30,
                srs_ease=2.8,
                srs_reps=9,
                srs_next_review=now,
                is_favourite=True,
                created_at=now,
                updated_at=now,
            )
        )

    with _client("team-test-member", team_id=team_id) as c:
        created = c.post(
            f"/api/v1/teams/{team_id}/knowledge/posts/share-word",
            json={"user_vocab_id": "team-test-word-1", "note": "Useful for Task 2"},
        )
        feed = c.get(f"/api/v1/teams/{team_id}/knowledge/posts")

    assert created.status_code == 201
    post = created.json()["post"]
    assert post["type"] == "shared_word"
    assert post["body"] == "Useful for Task 2"
    assert post["word_snapshot"]["word"] == "scalability"
    assert "srs_interval" not in post["word_snapshot"]
    assert "is_favourite" not in post["word_snapshot"]
    assert "user_note" not in post["word_snapshot"]

    assert feed.status_code == 200
    assert feed.json()["items"][0]["id"] == post["id"]


def test_member_saves_shared_team_word_idempotently() -> None:
    from services.db import get_sync_session
    from services.db.models import TeamKnowledgePost, TeamMember, User

    team_id = _create_team()
    _seed_user("team-test-member")
    now = datetime.now(timezone.utc)
    with get_sync_session() as s, s.begin():
        s.add(
            TeamMember(
                team_id=team_id,
                user_uid="team-test-member",
                role="member",
                joined_at=now,
            )
        )
        s.execute(
            update(User).where(User.id == "team-test-member").values(team_id=team_id),
        )
        s.add(
            TeamKnowledgePost(
                id="11111111-1111-1111-1111-111111111111",
                team_id=team_id,
                author_uid="team-test-owner",
                type="shared_word",
                category="vocabulary",
                title="coherence",
                body=None,
                source_user_vocab_id=None,
                word_snapshot={
                    "word": "coherence",
                    "definition_en": "logical connection",
                    "definition_vi": "su lien ket logic",
                    "ipa": "",
                    "part_of_speech": "noun",
                    "example_en": "The essay has coherence.",
                    "example_vi": "",
                    "topic": "writing",
                },
                status="active",
                created_at=now,
                updated_at=now,
            )
        )

    with _client("team-test-member", team_id=team_id) as c:
        first = c.post(
            f"/api/v1/teams/{team_id}/knowledge/posts/"
            "11111111-1111-1111-1111-111111111111/save-word"
        )
        second = c.post(
            f"/api/v1/teams/{team_id}/knowledge/posts/"
            "11111111-1111-1111-1111-111111111111/save-word"
        )

    assert first.status_code == 200
    assert first.json()["created"] is True
    assert second.status_code == 200
    assert second.json()["already_saved"] is True
    assert second.json()["word"]["word"] == "coherence"
