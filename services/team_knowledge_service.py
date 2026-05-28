"""Team knowledge feed service.

The feed is intentionally structured around learning objects. Shared
vocabulary is stored as a privacy-safe snapshot, so teammates never see
the sharer's SRS state, favourites, mistakes, review history, or private
notes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, delete, func, or_, select

from api.errors import ERR, ApiError
from services import firebase_service, word_service
from services.admin import audit_service
from services.db import get_sync_session
from services.db.models import (
    Team,
    TeamKnowledgePost,
    TeamKnowledgeReaction,
    TeamKnowledgeReply,
    TeamMember,
    Topic,
    User,
    UserVocabulary,
)

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


def _is_team_admin(session, team: Team, user_id: str) -> bool:
    if team.owner_uid == user_id:
        return True
    membership = session.get(TeamMember, {"team_id": team.id, "user_uid": user_id})
    return membership is not None and membership.role == "admin"


def _assert_can_delete_content(session, team: Team, user_id: str, author_uid: str) -> None:
    if author_uid == user_id or _is_team_admin(session, team, user_id):
        return
    raise ApiError(ERR.forbidden)


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
    reply_counts: dict[str, int] | None = None,
    helpful_counts: dict[str, int] | None = None,
    helpful_by_me: set[str] | None = None,
) -> dict[str, Any]:
    snapshot = post.word_snapshot or {}
    norm = word_service.normalize_word(str(snapshot.get("word") or ""))
    existing_word_id = saved_by_norm.get(norm)
    reply_counts = reply_counts or {}
    helpful_counts = helpful_counts or {}
    helpful_by_me = helpful_by_me or set()
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
        "word_snapshot": snapshot if snapshot else None,
        "saved_to_my_words": existing_word_id is not None,
        "existing_word_id": existing_word_id,
        "reply_count": reply_counts.get(post.id, 0),
        "helpful_count": helpful_counts.get(post.id, 0),
        "helpful_by_me": post.id in helpful_by_me,
        "created_at": post.created_at,
    }


def _author_names(session, posts: list[TeamKnowledgePost]) -> dict[str, str]:
    return _author_names_for_user_ids(session, {post.author_uid for post in posts})


def _author_names_for_user_ids(session, user_ids: set[str]) -> dict[str, str]:
    if not user_ids:
        return {}
    rows = session.execute(select(User.id, User.name).where(User.id.in_(user_ids))).all()
    return {str(user_id): str(name or "") for user_id, name in rows}


def _post_reply_counts(session, post_ids: list[str]) -> dict[str, int]:
    if not post_ids:
        return {}
    rows = session.execute(
        select(TeamKnowledgeReply.post_id, func.count())
        .where(
            TeamKnowledgeReply.post_id.in_(post_ids),
            TeamKnowledgeReply.status == "active",
        )
        .group_by(TeamKnowledgeReply.post_id)
    ).all()
    return {str(post_id): int(count) for post_id, count in rows}


def _helpful_counts(session, target_type: str, target_ids: list[str]) -> dict[str, int]:
    if not target_ids:
        return {}
    rows = session.execute(
        select(TeamKnowledgeReaction.target_id, func.count())
        .where(
            TeamKnowledgeReaction.target_type == target_type,
            TeamKnowledgeReaction.reaction == "helpful",
            TeamKnowledgeReaction.target_id.in_(target_ids),
        )
        .group_by(TeamKnowledgeReaction.target_id)
    ).all()
    return {str(target_id): int(count) for target_id, count in rows}


def _helpful_by_user(session, target_type: str, target_ids: list[str], user_id: str) -> set[str]:
    if not target_ids:
        return set()
    rows = session.execute(
        select(TeamKnowledgeReaction.target_id).where(
            TeamKnowledgeReaction.target_type == target_type,
            TeamKnowledgeReaction.reaction == "helpful",
            TeamKnowledgeReaction.user_uid == user_id,
            TeamKnowledgeReaction.target_id.in_(target_ids),
        )
    ).scalars().all()
    return {str(target_id) for target_id in rows}


def _reply_to_dict(
    reply: TeamKnowledgeReply,
    author_names: dict[str, str],
    helpful_counts: dict[str, int] | None = None,
    helpful_by_me: set[str] | None = None,
) -> dict[str, Any]:
    helpful_counts = helpful_counts or {}
    helpful_by_me = helpful_by_me or set()
    return {
        "id": reply.id,
        "post_id": reply.post_id,
        "team_id": reply.team_id,
        "author": {
            "user_id": reply.author_uid,
            "name": author_names.get(reply.author_uid) or reply.author_uid,
        },
        "body": reply.body,
        "helpful_count": helpful_counts.get(reply.id, 0),
        "helpful_by_me": reply.id in helpful_by_me,
        "created_at": reply.created_at,
    }


def _active_post(session, team_id: str, post_id: str) -> TeamKnowledgePost:
    post = session.execute(
        select(TeamKnowledgePost).where(
            TeamKnowledgePost.id == post_id,
            TeamKnowledgePost.team_id == team_id,
            TeamKnowledgePost.status == "active",
        )
    ).scalar_one_or_none()
    if post is None:
        raise ApiError(ERR.not_found)
    return post


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
        post_ids = [post.id for post in visible]
        saved_by_norm = _saved_word_lookup(session, user_id, visible)
        authors = _author_names(session, visible)
        reply_counts = _post_reply_counts(session, post_ids)
        helpful_counts = _helpful_counts(session, "post", post_ids)
        my_helpful = _helpful_by_user(session, "post", post_ids, user_id)
        items = [
            _post_to_dict(
                post,
                authors,
                saved_by_norm,
                reply_counts,
                helpful_counts,
                my_helpful,
            )
            for post in visible
        ]
        next_cursor = _make_cursor(visible[-1]) if len(posts) > limit and visible else None
        return {"items": items, "next_cursor": next_cursor}


def create_post(
    *,
    team_id: str,
    user_id: str,
    post_type: str,
    category: str,
    title: str,
    body: str,
    word_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    post_type = post_type.strip()
    category = category.strip() or "general"
    title = title.strip()
    body = body.strip()
    if post_type not in {"question", "note"}:
        raise ApiError(ERR.validation, field="type")
    if not title:
        raise ApiError(ERR.validation, field="title")
    if not body:
        raise ApiError(ERR.validation, field="body")
    now = _now()
    with get_sync_session() as session, session.begin():
        _assert_team_member(session, team_id, user_id)
        post = TeamKnowledgePost(
            team_id=team_id,
            author_uid=user_id,
            type=post_type,
            category=category,
            title=title,
            body=body,
            source_user_vocab_id=None,
            word_snapshot=_word_snapshot_from_context(word_context),
            status="active",
            created_at=now,
            updated_at=now,
        )
        session.add(post)
        session.flush()
        authors = _author_names(session, [post])
        payload = _post_to_dict(post, authors, {})

    audit_service.log_event(
        actor_uid=user_id,
        event_type="team.knowledge.post_created",
        target_kind="team",
        target_id=team_id,
        before=None,
        after={"post_id": payload["id"], "type": post_type},
    )
    return payload


def _word_snapshot_from_context(word_context: dict[str, Any] | None) -> dict[str, str]:
    if not word_context:
        return {}
    word = str(word_context.get("word") or "").strip()
    if not word:
        return {}
    return {
        "word": word[:120],
        "definition_en": str(word_context.get("definition_en") or "")[:500],
        "definition_vi": str(word_context.get("definition_vi") or "")[:500],
        "ipa": str(word_context.get("ipa") or "")[:120],
        "part_of_speech": str(word_context.get("part_of_speech") or "")[:80],
        "example_en": str(word_context.get("example_en") or "")[:500],
        "example_vi": str(word_context.get("example_vi") or "")[:500],
        "topic": str(word_context.get("topic") or "")[:120],
    }


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


def list_replies(
    *,
    team_id: str,
    post_id: str,
    user_id: str,
    limit: int,
    cursor: str | None = None,
) -> dict[str, Any]:
    parsed_cursor = _parse_cursor(cursor)
    with get_sync_session() as session:
        _assert_team_member(session, team_id, user_id)
        _active_post(session, team_id, post_id)
        filters = [
            TeamKnowledgeReply.team_id == team_id,
            TeamKnowledgeReply.post_id == post_id,
            TeamKnowledgeReply.status == "active",
        ]
        if parsed_cursor is not None:
            created_at, reply_id = parsed_cursor
            filters.append(
                or_(
                    TeamKnowledgeReply.created_at > created_at,
                    and_(
                        TeamKnowledgeReply.created_at == created_at,
                        TeamKnowledgeReply.id > reply_id,
                    ),
                )
            )
        replies = (
            session.execute(
                select(TeamKnowledgeReply)
                .where(*filters)
                .order_by(TeamKnowledgeReply.created_at.asc(), TeamKnowledgeReply.id.asc())
                .limit(limit + 1)
            )
            .scalars()
            .all()
        )
        visible = replies[:limit]
        reply_ids = [reply.id for reply in visible]
        authors = _author_names_for_user_ids(session, {reply.author_uid for reply in visible})
        helpful_counts = _helpful_counts(session, "reply", reply_ids)
        my_helpful = _helpful_by_user(session, "reply", reply_ids, user_id)
        items = [
            _reply_to_dict(reply, authors, helpful_counts, my_helpful)
            for reply in visible
        ]
        next_cursor = (
            f"{visible[-1].created_at.isoformat()}|{visible[-1].id}"
            if len(replies) > limit and visible
            else None
        )
        return {"items": items, "next_cursor": next_cursor}


def create_reply(
    *,
    team_id: str,
    post_id: str,
    user_id: str,
    body: str,
) -> dict[str, Any]:
    body = body.strip()
    if not body:
        raise ApiError(ERR.validation, field="body")
    now = _now()
    with get_sync_session() as session, session.begin():
        _assert_team_member(session, team_id, user_id)
        post = _active_post(session, team_id, post_id)
        post.updated_at = now
        reply = TeamKnowledgeReply(
            post_id=post_id,
            team_id=team_id,
            author_uid=user_id,
            body=body,
            status="active",
            created_at=now,
            updated_at=now,
        )
        session.add(reply)
        session.flush()
        authors = _author_names_for_user_ids(session, {user_id})
        payload = _reply_to_dict(reply, authors)

    audit_service.log_event(
        actor_uid=user_id,
        event_type="team.knowledge.reply_created",
        target_kind="team",
        target_id=team_id,
        before=None,
        after={"post_id": post_id, "reply_id": payload["id"]},
    )
    return payload


def _toggle_helpful(
    *,
    session,
    team_id: str,
    user_id: str,
    target_type: str,
    target_id: str,
) -> dict[str, Any]:
    existing = session.execute(
        select(TeamKnowledgeReaction).where(
            TeamKnowledgeReaction.team_id == team_id,
            TeamKnowledgeReaction.target_type == target_type,
            TeamKnowledgeReaction.target_id == target_id,
            TeamKnowledgeReaction.user_uid == user_id,
            TeamKnowledgeReaction.reaction == "helpful",
        )
    ).scalar_one_or_none()
    helpful_by_me = existing is None
    if existing is None:
        session.add(
            TeamKnowledgeReaction(
                team_id=team_id,
                target_type=target_type,
                target_id=target_id,
                user_uid=user_id,
                reaction="helpful",
                created_at=_now(),
            )
        )
    else:
        session.execute(delete(TeamKnowledgeReaction).where(TeamKnowledgeReaction.id == existing.id))
    session.flush()
    helpful_count = session.execute(
        select(func.count()).where(
            TeamKnowledgeReaction.team_id == team_id,
            TeamKnowledgeReaction.target_type == target_type,
            TeamKnowledgeReaction.target_id == target_id,
            TeamKnowledgeReaction.reaction == "helpful",
        )
    ).scalar_one()
    return {
        "target_type": target_type,
        "target_id": target_id,
        "helpful_count": int(helpful_count),
        "helpful_by_me": helpful_by_me,
    }


def toggle_post_helpful(
    *,
    team_id: str,
    post_id: str,
    user_id: str,
) -> dict[str, Any]:
    with get_sync_session() as session, session.begin():
        _assert_team_member(session, team_id, user_id)
        _active_post(session, team_id, post_id)
        return _toggle_helpful(
            session=session,
            team_id=team_id,
            user_id=user_id,
            target_type="post",
            target_id=post_id,
        )


def toggle_reply_helpful(
    *,
    team_id: str,
    post_id: str,
    reply_id: str,
    user_id: str,
) -> dict[str, Any]:
    with get_sync_session() as session, session.begin():
        _assert_team_member(session, team_id, user_id)
        _active_post(session, team_id, post_id)
        reply = session.execute(
            select(TeamKnowledgeReply).where(
                TeamKnowledgeReply.id == reply_id,
                TeamKnowledgeReply.post_id == post_id,
                TeamKnowledgeReply.team_id == team_id,
                TeamKnowledgeReply.status == "active",
            )
        ).scalar_one_or_none()
        if reply is None:
            raise ApiError(ERR.not_found)
        return _toggle_helpful(
            session=session,
            team_id=team_id,
            user_id=user_id,
            target_type="reply",
            target_id=reply_id,
        )


def delete_post(
    *,
    team_id: str,
    post_id: str,
    user_id: str,
) -> None:
    now = _now()
    with get_sync_session() as session, session.begin():
        team = _assert_team_member(session, team_id, user_id)
        post = _active_post(session, team_id, post_id)
        _assert_can_delete_content(session, team, user_id, post.author_uid)
        post.status = "deleted"
        post.updated_at = now

    audit_service.log_event(
        actor_uid=user_id,
        event_type="team.knowledge.post_deleted",
        target_kind="team",
        target_id=team_id,
        before={"post_id": post_id, "author_uid": post.author_uid},
        after={"post_id": post_id, "status": "deleted"},
    )


def delete_reply(
    *,
    team_id: str,
    post_id: str,
    reply_id: str,
    user_id: str,
) -> None:
    now = _now()
    with get_sync_session() as session, session.begin():
        team = _assert_team_member(session, team_id, user_id)
        _active_post(session, team_id, post_id)
        reply = session.execute(
            select(TeamKnowledgeReply).where(
                TeamKnowledgeReply.id == reply_id,
                TeamKnowledgeReply.post_id == post_id,
                TeamKnowledgeReply.team_id == team_id,
                TeamKnowledgeReply.status == "active",
            )
        ).scalar_one_or_none()
        if reply is None:
            raise ApiError(ERR.not_found)
        _assert_can_delete_content(session, team, user_id, reply.author_uid)
        reply.status = "deleted"
        reply.updated_at = now

    audit_service.log_event(
        actor_uid=user_id,
        event_type="team.knowledge.reply_deleted",
        target_kind="team",
        target_id=team_id,
        before={"post_id": post_id, "reply_id": reply_id, "author_uid": reply.author_uid},
        after={"post_id": post_id, "reply_id": reply_id, "status": "deleted"},
    )
