"""add_exam_analysis_chunks

Revision ID: 0fbc2e74e5e6
Revises: 5c36f4228dd8
Create Date: 2026-08-24 22:57:40.435622

"""
from typing import Sequence, Union

import pgvector.sqlalchemy
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0fbc2e74e5e6'
down_revision: Union[str, Sequence[str], None] = '5c36f4228dd8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Đoạn trích raw_markdown của ExamAnalysis đã đánh chỉ mục embedding (RAG thật) — chấm ngữ cảnh
    tài liệu gốc vào prompt sinh câu hỏi kiểm tra. Theo đúng tiền lệ HNSW cosine của
    e7b3f1a6d205_add_rag_content_chunks.py (bảng đó đã bị xóa hoàn toàn cùng tính năng course
    catalog cũ) — không tái sử dụng schema cũ vì FK trỏ tới các bảng không còn tồn tại.
    """
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "exam_analysis_chunks",
        sa.Column("exam_analysis_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(dim=768), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["exam_analysis_id"], ["exam_analyses.id"],
            name=op.f("fk_exam_analysis_chunks_exam_analysis_id_exam_analyses"), ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exam_analysis_chunks")),
        sa.UniqueConstraint(
            "exam_analysis_id", "chunk_index", name="uq_exam_analysis_chunks_analysis_chunk_index"
        ),
    )
    op.create_index(
        "ix_exam_analysis_chunks_exam_analysis_id", "exam_analysis_chunks", ["exam_analysis_id"]
    )
    op.execute(
        "CREATE INDEX ix_exam_analysis_chunks_embedding_hnsw ON exam_analysis_chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_exam_analysis_chunks_embedding_hnsw")
    op.drop_index("ix_exam_analysis_chunks_exam_analysis_id", table_name="exam_analysis_chunks")
    op.drop_table("exam_analysis_chunks")
