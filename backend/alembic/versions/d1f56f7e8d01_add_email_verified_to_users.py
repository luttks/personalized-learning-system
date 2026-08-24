"""add_email_verified_to_users

Revision ID: d1f56f7e8d01
Revises: 5467b113ab1a
Create Date: 2026-08-20 16:44:21.740441

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1f56f7e8d01'
down_revision: Union[str, Sequence[str], None] = '5467b113ab1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('email_verified', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Tài khoản đã tồn tại trước khi có bước xác thực OTP được coi là đã xác thực sẵn (grandfather
    # in) — chỉ tài khoản đăng ký MỚI sau migration này mới bắt buộc xác thực email.
    op.execute("UPDATE users SET email_verified = true")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'email_verified')
