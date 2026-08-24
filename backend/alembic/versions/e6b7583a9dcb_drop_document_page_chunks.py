"""drop_document_page_chunks

Revision ID: e6b7583a9dcb
Revises: 4719a24d272f
Create Date: 2026-08-23 13:23:18.230867

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'e6b7583a9dcb'
down_revision: Union[str, Sequence[str], None] = '4719a24d272f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Bỏ hẳn cơ chế RAG bằng embedding/pgvector cho tính năng nhảy đúng trang khi xem lại tài liệu
    gốc — thay bằng LLM tìm trích dẫn nguyên văn + so khớp chuỗi con trực tiếp (xem
    resolve_topic_locations_via_quotes trong app/services/exam_service.py). Endpoint embedding
    (gemini-embedding-001) có hạn mức gọi rất thấp trên tài khoản hiện tại, không dùng được ổn
    định trong thực tế. KHÔNG drop extension "vector" — khai báo độc lập trong database/init.sql,
    không thuộc vòng đời tính năng này.
    """
    op.drop_index(op.f('ix_document_page_chunks_exam_analysis_id'), table_name='document_page_chunks')
    op.drop_table('document_page_chunks')
    op.drop_column('exam_analyses', 'page_index_status')


def downgrade() -> None:
    """Downgrade schema — dựng lại y hệt những gì migration 4719a24d272f đã tạo."""
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
