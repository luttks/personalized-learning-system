"""add_roadmap_final_exams

Revision ID: 4d86172c690f
Revises: ae5c87f4932c
Create Date: 2026-08-24 21:24:48.653028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4d86172c690f'
down_revision: Union[str, Sequence[str], None] = 'ae5c87f4932c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Bảng mới cho bài thi chốt hạ cuối lộ trình (1 dòng/roadmap, khác PhaseAssessment vì không theo
    giai đoạn, không có pass_threshold/gate — xem docstring RoadmapFinalExam).
    """
    op.create_table(
        'roadmap_final_exams',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('roadmap_id', sa.UUID(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('questions_json', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('score_ratio', sa.Float(), nullable=True),
        sa.Column('attempts_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_attempted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('attempts_count >= 0', name=op.f('ck_roadmap_final_exams_attempts_non_negative')),
        sa.CheckConstraint('score_ratio IS NULL OR (score_ratio >= 0 AND score_ratio <= 1)', name=op.f('ck_roadmap_final_exams_score_range')),
        sa.ForeignKeyConstraint(['roadmap_id'], ['personalized_roadmaps.id'], name=op.f('fk_roadmap_final_exams_roadmap_id_personalized_roadmaps'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_roadmap_final_exams')),
        sa.UniqueConstraint('roadmap_id', name=op.f('uq_roadmap_final_exams_roadmap')),
    )
    op.create_index(op.f('ix_roadmap_final_exams_roadmap_id'), 'roadmap_final_exams', ['roadmap_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_roadmap_final_exams_roadmap_id'), table_name='roadmap_final_exams')
    op.drop_table('roadmap_final_exams')
