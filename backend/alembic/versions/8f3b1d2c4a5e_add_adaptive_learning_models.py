"""add adaptive learning models

Revision ID: 8f3b1d2c4a5e
Revises: 17c7cad1b896
Create Date: 2026-07-29 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "8f3b1d2c4a5e"
down_revision: str | Sequence[str] | None = "17c7cad1b896"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "learner_profiles",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("education_level", sa.String(100)),
        sa.Column("subject", sa.String(150)),
        sa.Column("learning_goal", sa.JSON(), nullable=False),
        sa.Column("deadline", sa.Date()),
        sa.Column("current_level", sa.String(100)),
        sa.Column("known_concepts", sa.JSON(), nullable=False),
        sa.Column("weak_concepts", sa.JSON(), nullable=False),
        sa.Column("misconceptions", sa.JSON(), nullable=False),
        sa.Column("minutes_per_day", sa.Integer()),
        sa.Column("days_per_week", sa.Integer()),
        sa.Column("available_periods", sa.JSON(), nullable=False),
        sa.Column("learning_preferences", sa.JSON(), nullable=False),
        sa.Column("diagnostic_results", sa.JSON(), nullable=False),
        sa.Column("confidence_scores", sa.JSON(), nullable=False),
        sa.Column("missing_fields", sa.JSON(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.CheckConstraint(
            "minutes_per_day >= 10 AND minutes_per_day <= 600",
            name=op.f("ck_learner_profiles_learner_minutes_per_day_range"),
        ),
        sa.CheckConstraint(
            "days_per_week >= 1 AND days_per_week <= 7",
            name=op.f("ck_learner_profiles_learner_days_per_week_range"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name=op.f("fk_learner_profiles_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learner_profiles")),
    )
    op.create_index(
        op.f("ix_learner_profiles_subject"), "learner_profiles", ["subject"]
    )
    op.create_index(
        op.f("ix_learner_profiles_user_id"), "learner_profiles", ["user_id"],
        unique=True,
    )

    op.create_table(
        "learner_evidence",
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("evidence_type", sa.String(50), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("topic_id", sa.String(255)),
        sa.Column("field_name", sa.String(100)),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["learner_id"], ["learner_profiles.id"],
            name=op.f("fk_learner_evidence_learner_id_learner_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_learner_evidence")),
    )
    op.create_index(
        op.f("ix_learner_evidence_learner_id"), "learner_evidence", ["learner_id"]
    )
    op.create_index(
        op.f("ix_learner_evidence_topic_id"), "learner_evidence", ["topic_id"]
    )

    op.create_table(
        "learner_topic_mastery",
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("topic_id", sa.String(255), nullable=False),
        sa.Column("mastery_score", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("repeated_errors", sa.Integer(), nullable=False),
        sa.Column("last_assessed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "mastery_score >= 0 AND mastery_score <= 1",
            name=op.f("ck_learner_topic_mastery_mastery_score_range"),
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_learner_topic_mastery_mastery_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"], ["learner_profiles.id"],
            name=op.f("fk_learner_topic_mastery_learner_id_learner_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "learner_id", "topic_id", name=op.f("pk_learner_topic_mastery")
        ),
    )

    op.create_table(
        "roadmaps",
        sa.Column("learner_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(150), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("deadline", sa.Date()),
        sa.Column("total_estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("profile_version", sa.Integer(), nullable=False),
        sa.Column("context_json", sa.JSON(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["learner_id"], ["learner_profiles.id"],
            name=op.f("fk_roadmaps_learner_id_learner_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roadmaps")),
    )
    op.create_index(op.f("ix_roadmaps_learner_id"), "roadmaps", ["learner_id"])

    op.create_table(
        "roadmap_items",
        sa.Column("roadmap_id", sa.UUID(), nullable=False),
        sa.Column("concept_id", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("session_number", sa.Integer(), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("activity_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("now()"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["roadmap_id"], ["roadmaps.id"],
            name=op.f("fk_roadmap_items_roadmap_id_roadmaps"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_roadmap_items")),
        sa.UniqueConstraint(
            "roadmap_id", "sequence", name="uq_roadmap_items_sequence"
        ),
    )
    op.create_index(
        op.f("ix_roadmap_items_roadmap_id"), "roadmap_items", ["roadmap_id"]
    )
    op.create_index(
        op.f("ix_roadmap_items_concept_id"), "roadmap_items", ["concept_id"]
    )


def downgrade() -> None:
    op.drop_table("roadmap_items")
    op.drop_table("roadmaps")
    op.drop_table("learner_topic_mastery")
    op.drop_table("learner_evidence")
    op.drop_table("learner_profiles")
