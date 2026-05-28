"""Team knowledge feed service.

The feed is intentionally structured around learning objects. Shared
vocabulary is stored as a privacy-safe snapshot, so teammates never see
the sharer's SRS state, favourites, mistakes, review history, or private
notes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, or_, select

from api.errors import ERR, ApiError
from services import firebase_service, word_service
from services.admin import audit_service
from services.db import get_sync_session
from services.db.models import Team, TeamKnowledgePost, TeamMember, Topic, User, UserVocabulary

SHARED_WORD_SOURCE_ID = 3
VOCAB_LIMITS_BY_PLAN = {
    "free": 100,
    "personal_pro": 1000,
    "team_member": 5000,
    "org_member": 10000,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _assert_team_member(session, team_id: str, user_id: str) -> Team:
    team = session.get(Team, team_id)
    if team is None:
        raise ApiError(ERR.admin_target_not_found, target_kind="team", target_id=team_id)
    membership = session.get(TeamMember, {"team_id": team_id, "user_uid": user_id})
    if membership is None and team.owner_uid != user_id:
        raise ApiError(ERR.forbidden)
    return team


def _parse_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    if not cursor:
        return None
    try:
        created_raw, post_id = cursor.split("|", 1)
        return datetime.fromisoformat(created_raw), post_id
    except ValueError:
        raise ApiError(ERR.validation, field="cursor")


def _make_cursor(post: TeamKnowledgePost) -> str:
    return f"{post.created_at.isoformat()}|{post.id}"


def _snapshot_from_word(word: UserVocabulary, topic_slug: str) -> dict[str, str]:
    return {
        "word": word.word,
        "definition_en": word.definition_en,
        "definition_vi": word.definition_vi,
        "ipa": word.ipa,
        "part_of_speech": word.part_of_speech,
        "example_en": word.example_en,
        "example_vi": word.example_vi,
        "topic": topic_slug,
    }


def _word_data_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "word": str(snapshot.get("word") or ""),
        "definition": str(snapshot.get("definition_en") or ""),
        "definition_vi": str(snapshot.get("definition_vi") or ""),
        "ipa": str(snapshot.get("ipa") or ""),
        "part_of_speech": str(snapshot.get("part_of_speech") or ""),
        "topic": str(snapshot.get("topic") or ""),
        "example_en": str(snapshot.get("example_en") or ""),
        "example_vi": str(snapshot.get("example_vi") or ""),
        "source": SHARED_WORD_SOURCE_ID,
    }


def _saved_word_lookup(session, user_id: str, posts: list[TeamKnowledgePost]) -> dict[str, str]:
    norms = {
        word_service.normalize_word(str((post.word_snapshot or {}).get("word") or ""))
        for post in posts
        if post.type == "shared_word"
    }
    norms.discard("")
    if not norms:
        return {}
    rows = session.execute(
        select(UserVocabulary.normalized_word, UserVocabulary.id).where(
            UserVocabulary.user_id == user_id,
            UserVocabulary.archived_at.is_(None),
            UserVocabulary.normalized_word.in_(norms),
        )
    ).all()
    return {str(norm): str(word_id) for norm, word_id in rows}


def _post_to_dict(
    post: TeamKnowledgePost,
    author_names: dict[str, str],
    saved_by_norm: dict[str, str],
) -> dict[str, Any]:
    snapshot = post.word_snapshot or {}
    norm = word_service.normalize_word(str(snapshot.get("word") or ""))
    existing_word_id = saved_by_norm.get(norm)
    return {
        "id": post.id,
        "team_id": post.team_id,
        "type": post.type,
        "category": post.category,
        "title": post.title,
        "body": post.body,
        "author": {
            "user_id": post.author_uid,
            "name": author_names.get(post.author_uid) or post.author_uid,
        },
        "word_snapshot": snapshot if post.type == "shared_word" else None,
        "saved_to_my_words": existing_word_id is not None,
        "existing_word_id": existing_word_id,
        "created_at": post.created_at,
    }


def _author_names(session, posts: list[TeamKnowledgePost]) -> dict[str, str]:
    author_ids = {post.author_uid for post in posts}
    if not author_ids:
        return {}
    rows = session.execute(select(User.id, User.name).where(User.id.in_(author_ids))).all()
    return {str(user_id): str(name or "") for user_id, name in rows}


def list_posts(
    *,
    team_id: str,
    user_id: str,
    limit: int,
    cursor: str | None = None,
) -> dict[str, Any]:
    parsed_cursor = _parse_cursor(cursor)
    with get_sync_session() as session:
        _assert_team_member(session, team_id, user_id)
        filters = [
            TeamKnowledgePost.team_id == team_id,
            TeamKnowledgePost.status == "active",
        ]
        if parsed_cursor is not None:
            created_at, post_id = parsed_cursor
            filters.append(
                or_(
                    TeamKnowledgePost.created_at < created_at,
                    and_(
                        TeamKnowledgePost.created_at == created_at,
                        TeamKnowledgePost.id < post_id,
                    ),
                )
            )
        posts = (
            session.execute(
                select(TeamKnowledgePost)
                .where(*filters)
                .order_by(TeamKnowledgePost.created_at.desc(), TeamKnowledgePost.id.desc())
                .limit(limit + 1)
            )
            .scalars()
            .all()
        )
        visible = posts[:limit]
        saved_by_norm = _saved_word_lookup(session, user_id, visible)
        authors = _author_names(session, visible)
        items = [_post_to_dict(post, authors, saved_by_norm) for post in visible]
        next_cursor = _make_cursor(visible[-1]) if len(posts) > limit and visible else None
        return {"items": items, "next_cursor": next_cursor}


def share_word(
    *,
    team_id: str,
    user_id: str,
    user_vocab_id: str | None,
    word_text: str | None,
    note: str,
) -> dict[str, Any]:
    note = note.strip()
    normalized = word_service.normalize_word(word_text or "")
    if not user_vocab_id and not normalized:
        raise ApiError(ERR.validation, field="user_vocab_id")
    now = _now()
    with get_sync_session() as session, session.begin():
        _assert_team_member(session, team_id, user_id)
        filters = [
            UserVocabulary.user_id == user_id,
            UserVocabulary.archived_at.is_(None),
        ]
        if user_vocab_id:
            filters.append(UserVocabulary.id == user_vocab_id)
        else:
            filters.append(UserVocabulary.normalized_word == normalized)
        word = session.execute(
            select(UserVocabulary).where(*filters)
        ).scalar_one_or_none()
        if word is None:
            raise ApiError(ERR.vocab_word_not_found)
        topic_slug = session.execute(
            select(Topic.slug).where(Topic.id == word.topic_id)
        ).scalar_one_or_none() or ""
        post = TeamKnowledgePost(
            team_id=team_id,
            author_uid=user_id,
            type="shared_word",
            category="vocabulary",
            title=word.word,
            body=note or None,
            source_user_vocab_id=word.id,
            word_snapshot=_snapshot_from_word(word, topic_slug),
            status="active",
            created_at=now,
            updated_at=now,
        )
        session.add(post)
        session.flush()
        authors = _author_names(session, [post])
        saved_by_norm = _saved_word_lookup(session, user_id, [post])
        payload = _post_to_dict(post, authors, saved_by_norm)

    audit_service.log_event(
        actor_uid=user_id,
        event_type="team.knowledge.word_shared",
        target_kind="team",
        target_id=team_id,
        before=None,
        after={"post_id": payload["id"], "word": payload["word_snapshot"]["word"]},
    )
    return payload


def save_shared_word(
    *,
    team_id: str,
    post_id: str,
    user: dict,
) -> dict[str, Any]:
    user_id = str(user["id"])
    with get_sync_session() as session:
        _assert_team_member(session, team_id, user_id)
        post = session.execute(
            select(TeamKnowledgePost).where(
                TeamKnowledgePost.id == post_id,
                TeamKnowledgePost.team_id == team_id,
                TeamKnowledgePost.status == "active",
                TeamKnowledgePost.type == "shared_word",
            )
        ).scalar_one_or_none()
        if post is None:
            raise ApiError(ERR.not_found)
        snapshot = dict(post.word_snapshot or {})

    normalized = word_service.normalize_word(str(snapshot.get("word") or ""))
    if not normalized:
        raise ApiError(ERR.vocab_word_empty)

    existing = firebase_service.get_word_by_text(user_id, normalized)
    if existing:
        return {"created": False, "already_saved": True, "word": existing}

    cap = VOCAB_LIMITS_BY_PLAN.get(user.get("plan") or "free", VOCAB_LIMITS_BY_PLAN["free"])
    used = firebase_service.count_user_vocabulary(user_id)
    if used >= cap:
        raise ApiError(
            ERR.vocab_private_word_limit_exceeded,
            plan=user.get("plan", "free"),
            limit=cap,
            used=used,
        )

    word_id, created = firebase_service.add_word_if_not_exists(
        user_id,
        _word_data_from_snapshot(snapshot),
    )
    saved = firebase_service.get_word_by_id(user_id, word_id) or {
        "id": word_id,
        **_word_data_from_snapshot(snapshot),
    }
    audit_service.log_event(
        actor_uid=user_id,
        event_type="team.knowledge.word_saved",
        target_kind="team",
        target_id=team_id,
        before=None,
        after={"post_id": post_id, "word_id": word_id, "created": created},
    )
    return {"created": created, "already_saved": not created, "word": saved}
