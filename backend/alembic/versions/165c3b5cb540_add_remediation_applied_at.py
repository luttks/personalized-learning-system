"""add_remediation_applied_at

Revision ID: 165c3b5cb540
Revises: e6b7583a9dcb
Create Date: 2026-08-24 06:26:51.582973

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '165c3b5cb540'
down_revision: Union[str, Sequence[str], None] = 'e6b7583a9dcb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Cột đánh dấu đã chèn nội dung củng cố + xếp lại lịch các giai đoạn sau khi rớt lần đầu ở giai
    đoạn này (xem apply_phase_remediation trong app/services/exam_service.py) — bảo vệ chống áp
    dụng lại lần 2 nếu task Celery tự retry/redeliver, hoặc 2 request nộp bài chạy đồng thời.
    """
    op.add_column(
        'phase_assessments',
        sa.Column('remediation_applied_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('phase_assessments', 'remediation_applied_at')
