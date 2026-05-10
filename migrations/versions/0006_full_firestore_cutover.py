"""Full Firestore cut-off — migrate all 17 collections to Postgres (M8 #234)

Revision ID: 0006_full_firestore_cutover
Revises: 0005_ai_routing_fix
Create Date: 2026-05-10

Schemas calibrated against actual prod Firestore export (`.fs_export/`,
762 rows / 20 collection queries on 2026-05-10). Each table mirrors the
shape of the data already in Firestore — the migration script does
straight 1-1 field mapping, with the few app-side improvements
documented below applied at insert time:

  - user_vocabulary: synthesize `normalized_word`, map `topic` display
    name → topic_id, fold legacy `definition` into `definition_en`,
    drop dead fields `times_correct`/`times_incorrect`, default
    `source = 1` for legacy rows (real provenance unrecoverable).
  - group_challenges: assign new UUIDs as `id` (Firestore used the date
    string as docid; PG splits id from date so future schemas can carry
    multiple challenges/day if needed).
  - groups: keep both `owner_telegram_id` (legacy bot data) and
    `owner_uid` (M14 web auth field, NULL until creator runs /start).

Per refinement (#234):
  * No dual-write — straight cutover.
  * ID columns are sa.Text() to preserve Firestore docid traceability.
    review_events uses BIGSERIAL because it's new (no FS predecessor).
  * user_id FK is sa.Text() matching users.id (set in 0001_users_baseline).
  * group_id is sa.BigInteger() matching Telegram chat_id.
  * JSONB tail for schema-loose payloads.
  * review_events is immutable: RULEs block UPDATE/DELETE.
  * Soft-delete via archived_at on user_vocabulary; partial indexes
    filter archived rows out of hot paths.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_full_firestore_cutover"
down_revision: Union[str, None] = "0005_ai_routing_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 12 fixed topic slugs. Names mirror web/public/locales/{en,vi}/vocab.json
# topicNames. Sort order = alphabetical, ids dense from 1.
TOPICS_SEED: list[tuple[int, str, str, str]] = [
    (1, "arts", "Arts & Creativity", "Nghệ thuật & Sáng tạo"),
    (2, "economy", "Economy & Business", "Kinh tế & Kinh doanh"),
    (3, "education", "Education & Learning", "Giáo dục & Học tập"),
    (4, "environment", "Environment & Nature", "Môi trường & Thiên nhiên"),
    (5, "food", "Food & Agriculture", "Ẩm thực & Nông nghiệp"),
    (6, "government", "Government & Law", "Chính phủ & Pháp luật"),
    (7, "health", "Health & Wellbeing", "Sức khỏe & Wellbeing"),
    (8, "media", "Media & Communication", "Truyền thông & Giao tiếp"),
    (9, "science", "Science & Research", "Khoa học & Nghiên cứu"),
    (10, "society", "Society & Culture", "Xã hội & Văn hóa"),
    (11, "technology", "Technology & Innovation", "Công nghệ & Đổi mới"),
    (12, "travel", "Travel & Tourism", "Du lịch"),
]


def _jsonb(default: str = "'[]'::jsonb"):
    """Helper: JSONB column with server_default."""
    return sa.text(default)


def upgrade() -> None:  # noqa: PLR0915 — single-revision schema bootstrap
    # ── set_updated_at function (shared trigger) ────────────────────────
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # ── Block A — User-data hot path ────────────────────────────────────

    op.create_table(
        "topics",
        sa.Column("id", sa.SmallInteger(), primary_key=True),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("name_en", sa.Text(), nullable=False),
        sa.Column("name_vi", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
    )
    bind = op.get_bind()
    for tid, slug, name_en, name_vi in TOPICS_SEED:
        bind.execute(
            sa.text(
                "INSERT INTO topics (id, slug, name_en, name_vi, sort_order) "
                "VALUES (:id, :slug, :en, :vi, :ord)"
            ),
            {"id": tid, "slug": slug, "en": name_en, "vi": name_vi, "ord": tid},
        )

    op.create_table(
        "user_vocabulary",
        sa.Column("id", sa.Text(), primary_key=True),  # FS docid
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("word", sa.Text(), nullable=False),
        # NFC + lower + strip-punct dedupe key. UNIQUE below kills race-dupe.
        sa.Column("normalized_word", sa.Text(), nullable=False),
        sa.Column(
            "topic_id",
            sa.SmallInteger(),
            sa.ForeignKey("topics.id"),
            nullable=False,
        ),
        sa.Column("definition_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("definition_vi", sa.Text(), nullable=False, server_default=""),
        sa.Column("ipa", sa.Text(), nullable=False, server_default=""),
        sa.Column("part_of_speech", sa.Text(), nullable=False, server_default=""),
        sa.Column("example_en", sa.Text(), nullable=False, server_default=""),
        sa.Column("example_vi", sa.Text(), nullable=False, server_default=""),
        sa.Column("user_note", sa.Text(), nullable=False, server_default=""),
        # 1=daily, 2=quiz, 3=manual, 4=reading
        sa.Column("source", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.CheckConstraint("source BETWEEN 1 AND 4", name="ck_user_vocabulary_source"),
        # SRS state
        sa.Column("srs_interval", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("srs_ease", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("srs_reps", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("srs_next_review", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "normalized_word", name="uq_user_vocab_normalized"),
    )
    op.create_index(
        "ix_user_vocabulary_due",
        "user_vocabulary",
        ["user_id", "srs_next_review"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.create_index(
        "ix_user_vocabulary_topic",
        "user_vocabulary",
        ["user_id", "topic_id"],
        postgresql_where=sa.text("archived_at IS NULL"),
    )
    op.execute(
        "CREATE TRIGGER trg_user_vocabulary_updated_at "
        "BEFORE UPDATE ON user_vocabulary "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    op.create_table(
        "quiz_history",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("quiz_type", sa.Text(), nullable=False),  # FS field: `type`
        sa.Column("is_correct", sa.Boolean(), nullable=False),
        sa.Column(
            "is_challenge",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("word_id", sa.Text(), nullable=True),
        # Catch-all for question, user_answer, correct_answer, etc.
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_quiz_history_user_created",
        "quiz_history",
        ["user_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "writing_history",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_type", sa.Text(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=True),
        # FS calls this `text`. essay_text is the canonical PG name.
        sa.Column("essay_text", sa.Text(), nullable=True),
        sa.Column("original_text", sa.Text(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("overall_band", sa.Float(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("summary_vi", sa.Text(), nullable=True),
        sa.Column("scores", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "criterion_feedback", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "paragraph_annotations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        # Catch-all for any feedback fields not split out above.
        sa.Column("feedback", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "shared_to_group",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_writing_history_user_created",
        "writing_history",
        ["user_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "user_daily_words",
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("words", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("user_id", "date", name="pk_user_daily_words"),
    )

    op.create_table(
        "listening_history",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("exercise_type", sa.Text(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column("band", sa.Float(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=True),
        sa.Column("total", sa.Integer(), nullable=True),
        sa.Column("duration_estimate_sec", sa.Integer(), nullable=True),
        sa.Column(
            "submitted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        # Catch-all for transcript, blanks, questions, user_answers,
        # gap_fill_results, comprehension_results, display_text, user_indices.
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_listening_history_user_created",
        "listening_history",
        ["user_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "review_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        # NO FK on user_id: append-only audit log persists past user
        # deletion. The DO-INSTEAD-NOTHING rules below would also collide
        # with FK referential-integrity DELETE-cascade checks.
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("user_vocab_id", sa.Text(), nullable=False),
        sa.Column("result", sa.SmallInteger(), nullable=False),
        sa.Column("source", sa.SmallInteger(), nullable=False),
        sa.CheckConstraint("result BETWEEN 0 AND 5", name="ck_review_events_result"),
        sa.CheckConstraint("source BETWEEN 1 AND 4", name="ck_review_events_source"),
        sa.Column("srs_interval_before", sa.Integer(), nullable=True),
        sa.Column("srs_interval_after", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_review_events_user_created",
        "review_events",
        ["user_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_review_events_vocab_created",
        "review_events",
        ["user_vocab_id", sa.text("created_at DESC")],
    )
    op.execute(
        "CREATE RULE no_update_review_events AS ON UPDATE TO review_events DO INSTEAD NOTHING"
    )
    op.execute(
        "CREATE RULE no_delete_review_events AS ON DELETE TO review_events DO INSTEAD NOTHING"
    )

    # ── Block B — Bot-owned group state ─────────────────────────────────

    op.create_table(
        "groups",
        sa.Column("id", sa.BigInteger(), primary_key=True),  # Telegram chat_id
        sa.Column("default_band", sa.Float(), nullable=True),
        sa.Column("daily_time", sa.Text(), nullable=True),
        sa.Column("challenge_time", sa.Text(), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=True),
        sa.Column("challenge_question_count", sa.SmallInteger(), nullable=True),
        sa.Column("word_count", sa.SmallInteger(), nullable=True),
        sa.Column("owner_telegram_id", sa.BigInteger(), nullable=True),
        # M14 web-side owner uid; NULL until creator runs /start in group.
        sa.Column("owner_uid", sa.Text(), nullable=True),
        sa.Column(
            "topics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        # FIFO ring of last-N topics for rotation (US-#226), capped at
        # RECENT_TOPICS_KEEP=5 in app code.
        sa.Column(
            "recent_topics",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.execute(
        "CREATE TRIGGER trg_groups_updated_at "
        "BEFORE UPDATE ON groups "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    op.create_table(
        "group_members",
        sa.Column(
            "group_id",
            sa.BigInteger(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False, server_default="member"),
        sa.CheckConstraint(
            "role IN ('owner', 'admin', 'member')", name="ck_group_members_role"
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("group_id", "telegram_id", name="pk_group_members"),
    )

    op.create_table(
        "group_daily_words",
        sa.Column(
            "group_id",
            sa.BigInteger(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("words", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("group_id", "date", name="pk_group_daily_words"),
    )

    op.create_table(
        "group_challenges",
        # New UUID assigned at migration time. Firestore used `date` as
        # docid; PG splits id from date to allow >1 challenge/day later.
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "group_id",
            sa.BigInteger(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.CheckConstraint(
            "status IN ('active', 'closed', 'cancelled')",
            name="ck_group_challenges_status",
        ),
        sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "participants",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("group_id", "date", name="uq_group_challenges_per_day"),
    )

    op.create_table(
        "group_challenge_answers",
        sa.Column(
            "challenge_id",
            sa.Text(),
            sa.ForeignKey("group_challenges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # TEXT — answerer is Telegram int (mostly) or web auth_uid
        sa.Column("user_id", sa.Text(), nullable=False),
        # Map of {q_idx: bool} — question_index → correct
        sa.Column(
            "responses",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("display_name", sa.Text(), nullable=True),  # M14 #229
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint(
            "challenge_id", "user_id", name="pk_group_challenge_answers"
        ),
    )

    # ── Block C — User session state (ephemeral, TTL'd) ─────────────────

    op.create_table(
        "quiz_sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "answered_ids",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_quiz_sessions_created_at", "quiz_sessions", ["created_at"])

    op.create_table(
        "reading_sessions",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("passage_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="in_progress"),
        sa.CheckConstraint(
            "status IN ('in_progress', 'submitted', 'expired')",
            name="ck_reading_sessions_status",
        ),
        sa.Column("questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        # answer_key kept on the session row at start so the grade is
        # deterministic even if the global reading_questions row changes.
        sa.Column(
            "answer_key", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "user_answers", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        # Filled at submit time (band, breakdown, etc.).
        sa.Column("grade", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_reading_sessions_started_at", "reading_sessions", ["started_at"]
    )
    op.execute(
        "CREATE TRIGGER trg_reading_sessions_updated_at "
        "BEFORE UPDATE ON reading_sessions "
        "FOR EACH ROW EXECUTE FUNCTION set_updated_at()"
    )

    # ── Block D — Analytics / snapshots ─────────────────────────────────

    op.create_table(
        "daily_plans",
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        # Array of activity dicts: {id, type, route, description, completed,
        # estimated_minutes, ...}. App-side schema, not normalized further.
        sa.Column("activities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("cap_minutes", sa.SmallInteger(), nullable=True),
        sa.Column("completed_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("total_minutes", sa.SmallInteger(), nullable=True),
        sa.Column("days_until_exam", sa.SmallInteger(), nullable=True),
        sa.Column(
            "exam_urgent",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("user_id", "date", name="pk_daily_plans"),
    )

    op.create_table(
        "progress_snapshots",
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("overall_band", sa.Float(), nullable=True),
        sa.Column("target_band", sa.Float(), nullable=True),
        # {writing: {band, sample_size}, vocabulary: {...}, listening: {...},
        #  reading: {...}, quiz: {...}}
        sa.Column("skills", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("user_id", "date", name="pk_progress_snapshots"),
    )

    op.create_table(
        "progress_recommendations",
        sa.Column(
            "user_id",
            sa.Text(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # ISO week key like "2026-W16". Stored as TEXT to match Firestore
        # docid format and avoid week-arithmetic ambiguity.
        sa.Column("week_key", sa.Text(), nullable=False),
        # Array of {skill, tip_vi, tip_en, ...} dicts.
        sa.Column("tips", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "week_key", name="pk_progress_recommendations"
        ),
    )

    # Populated by nightly cron from review_events (and quiz/writing/etc.)
    # — cheap dashboard aggregation.
    op.create_table(
        "daily_review_snapshots",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("reviews_done", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reviews_correct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("words_added", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("study_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "snapshot_date", name="pk_daily_review_snapshots"
        ),
    )

    # ── Block E — Static content + system ───────────────────────────────

    op.create_table(
        "reading_questions",
        sa.Column("passage_id", sa.Text(), primary_key=True),
        # Client-safe questions (no answer key inline).
        sa.Column(
            "questions_client",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        # Server-side answer key with explanations. NEVER serialize to client.
        sa.Column(
            "answer_key", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "cached_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "enriched_words",
        sa.Column("word", sa.Text(), primary_key=True),
        sa.Column("ipa", sa.Text(), nullable=True),
        sa.Column("part_of_speech", sa.Text(), nullable=True),
        sa.Column("definition_en", sa.Text(), nullable=True),
        sa.Column("definition_vi", sa.Text(), nullable=True),
        sa.Column("syllable_stress", sa.Text(), nullable=True),
        sa.Column("ielts_tip", sa.Text(), nullable=True),
        sa.Column(
            "examples_by_band", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "collocations", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "word_family", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "cached_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_table(
        "feature_flags",
        sa.Column("name", sa.Text(), primary_key=True),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "kill_switch",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "rollout_pct", sa.SmallInteger(), nullable=False, server_default="0"
        ),
        sa.Column(
            "uid_allowlist",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "rollout_pct BETWEEN 0 AND 100", name="ck_feature_flags_rollout_pct"
        ),
    )

    # ── Block F — Ephemeral auth ────────────────────────────────────────

    op.create_table(
        "auth_link_codes",
        sa.Column("code", sa.Text(), primary_key=True),
        # Source of truth in Firestore is `telegram_id` (not user_id).
        # The code links a DM /start flow to a web auth grant.
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_auth_link_codes_expires_at", "auth_link_codes", ["expires_at"])


def downgrade() -> None:
    # Reverse order of creation to satisfy FK dependencies.
    op.drop_index("ix_auth_link_codes_expires_at", table_name="auth_link_codes")
    op.drop_table("auth_link_codes")

    op.drop_table("feature_flags")
    op.drop_table("enriched_words")
    op.drop_table("reading_questions")

    op.drop_table("daily_review_snapshots")
    op.drop_table("progress_recommendations")
    op.drop_table("progress_snapshots")
    op.drop_table("daily_plans")

    op.execute("DROP TRIGGER IF EXISTS trg_reading_sessions_updated_at ON reading_sessions")
    op.drop_index("ix_reading_sessions_started_at", table_name="reading_sessions")
    op.drop_table("reading_sessions")
    op.drop_index("ix_quiz_sessions_created_at", table_name="quiz_sessions")
    op.drop_table("quiz_sessions")

    op.drop_table("group_challenge_answers")
    op.drop_table("group_challenges")
    op.drop_table("group_daily_words")
    op.drop_table("group_members")
    op.execute("DROP TRIGGER IF EXISTS trg_groups_updated_at ON groups")
    op.drop_table("groups")

    op.execute("DROP RULE IF EXISTS no_delete_review_events ON review_events")
    op.execute("DROP RULE IF EXISTS no_update_review_events ON review_events")
    op.drop_index("ix_review_events_vocab_created", table_name="review_events")
    op.drop_index("ix_review_events_user_created", table_name="review_events")
    op.drop_table("review_events")

    op.drop_index(
        "ix_listening_history_user_created", table_name="listening_history"
    )
    op.drop_table("listening_history")

    op.drop_table("user_daily_words")

    op.drop_index("ix_writing_history_user_created", table_name="writing_history")
    op.drop_table("writing_history")

    op.drop_index("ix_quiz_history_user_created", table_name="quiz_history")
    op.drop_table("quiz_history")

    op.execute("DROP TRIGGER IF EXISTS trg_user_vocabulary_updated_at ON user_vocabulary")
    op.drop_index("ix_user_vocabulary_topic", table_name="user_vocabulary")
    op.drop_index("ix_user_vocabulary_due", table_name="user_vocabulary")
    op.drop_table("user_vocabulary")

    op.drop_table("topics")

    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
