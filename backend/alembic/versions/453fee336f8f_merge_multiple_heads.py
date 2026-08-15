"""merge multiple heads

Revision ID: 453fee336f8f
Revises: 9b35b227a0b5, a8f3b2c1d490
Create Date: 2026-08-13 04:51:24.332541

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '453fee336f8f'
down_revision: Union[str, Sequence[str], None] = ('9b35b227a0b5', 'a8f3b2c1d490')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
