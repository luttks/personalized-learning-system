"""add_document_page_chunks

Revision ID: 4719a24d272f
Revises: 50f622695282
Create Date: 2026-08-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy

# revision identifiers, used by Alembic.
revision: str = '4719a24d272f'
down_revision: Union[str, Sequence[str], None] = '50f622695282'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # pgvector đã bật qua database/init.sql — khai báo lại cho idempotent/an toàn khi chạy migration
    # trên một DB mới chưa từng chạy init.sql (VD môi trường test).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        'exam_analyses',
        sa.Column('page_index_status', sa.String(length=20), nullable=False, server_default='pending'),
    )

    op.create_table(
        'document_page_chunks',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('exam_analysis_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=False),
        sa.Column('page_number_end', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(768), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('page_number >= 1', name=op.f('ck_document_page_chunks_page_number_positive')),
        sa.CheckConstraint('page_number_end >= page_number', name=op.f('ck_document_page_chunks_page_range_valid')),
        sa.ForeignKeyConstraint(
            ['exam_analysis_id'], ['exam_analyses.id'],
            name=op.f('fk_document_page_chunks_exam_analysis_id_exam_analyses'), ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_document_page_chunks')),
    )
    op.create_index(
        op.f('ix_document_page_chunks_exam_analysis_id'), 'document_page_chunks', ['exam_analysis_id'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_document_page_chunks_exam_analysis_id'), table_name='document_page_chunks')
    op.drop_table('document_page_chunks')
    op.drop_column('exam_analyses', 'page_index_status')
