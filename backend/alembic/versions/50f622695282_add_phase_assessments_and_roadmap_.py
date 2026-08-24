"""add_phase_assessments_and_roadmap_apply_fields

Revision ID: 50f622695282
Revises: f475c2e275d3
Create Date: 2026-08-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '50f622695282'
down_revision: Union[str, Sequence[str], None] = 'f475c2e275d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'personalized_roadmaps',
        sa.Column('applied_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f('ix_personalized_roadmaps_applied_at'),
        'personalized_roadmaps', ['applied_at'], unique=False,
    )
    op.add_column(
        'personalized_roadmaps',
        sa.Column('current_phase_number', sa.Integer(), nullable=False, server_default='1'),
    )
    op.add_column(
        'personalized_roadmaps',
        sa.Column('last_reminder_sent_at', sa.Date(), nullable=True),
    )

    op.create_table(
        'phase_assessments',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('roadmap_id', sa.UUID(), nullable=False),
        sa.Column('phase_number', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('pass_threshold', sa.Float(), nullable=False),
        sa.Column('questions_json', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('score_ratio', sa.Float(), nullable=True),
        sa.Column('attempts_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('manually_unlocked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_attempted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('phase_number >= 1', name=op.f('ck_phase_assessments_phase_number_positive')),
        sa.CheckConstraint('attempts_count >= 0', name=op.f('ck_phase_assessments_attempts_non_negative')),
        sa.CheckConstraint('pass_threshold >= 0 AND pass_threshold <= 1', name=op.f('ck_phase_assessments_threshold_range')),
        sa.CheckConstraint('score_ratio IS NULL OR (score_ratio >= 0 AND score_ratio <= 1)', name=op.f('ck_phase_assessments_score_range')),
        sa.ForeignKeyConstraint(['roadmap_id'], ['personalized_roadmaps.id'], name=op.f('fk_phase_assessments_roadmap_id_personalized_roadmaps'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_phase_assessments')),
        sa.UniqueConstraint('roadmap_id', 'phase_number', name=op.f('uq_phase_assessments_roadmap_phase')),
    )
    op.create_index(op.f('ix_phase_assessments_roadmap_id'), 'phase_assessments', ['roadmap_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_phase_assessments_roadmap_id'), table_name='phase_assessments')
    op.drop_table('phase_assessments')
    op.drop_column('personalized_roadmaps', 'last_reminder_sent_at')
    op.drop_column('personalized_roadmaps', 'current_phase_number')
    op.drop_index(op.f('ix_personalized_roadmaps_applied_at'), table_name='personalized_roadmaps')
    op.drop_column('personalized_roadmaps', 'applied_at')
