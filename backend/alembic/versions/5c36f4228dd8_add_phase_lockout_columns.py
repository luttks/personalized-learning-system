"""add_phase_lockout_columns

Revision ID: 5c36f4228dd8
Revises: 4d86172c690f
Create Date: 2026-08-24 21:24:48.653028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5c36f4228dd8'
down_revision: Union[str, Sequence[str], None] = '4d86172c690f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    2 cột mới cho cơ chế "khóa + học lại" khi rớt sau khi bỏ qua giai đoạn trước đang hổng kiến
    thức (status mới 'locked_for_retry' — không cần migration riêng vì status là String(20) không
    có CheckConstraint giới hạn giá trị).
    """
    op.add_column('phase_assessments', sa.Column('retry_unlock_at', sa.Date(), nullable=True))
    op.add_column('phase_assessments', sa.Column('last_boost_reminder_sent_at', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('phase_assessments', 'last_boost_reminder_sent_at')
    op.drop_column('phase_assessments', 'retry_unlock_at')
