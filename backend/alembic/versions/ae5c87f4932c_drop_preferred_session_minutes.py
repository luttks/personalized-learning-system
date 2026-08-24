"""drop_preferred_session_minutes

Revision ID: ae5c87f4932c
Revises: 165c3b5cb540
Create Date: 2026-08-24 20:10:05.798139

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae5c87f4932c'
down_revision: Union[str, Sequence[str], None] = '165c3b5cb540'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Xóa preferred_session_minutes ("Thời lượng mỗi phiên") khỏi student_profiles — xác nhận qua
    grep toàn bộ codebase: cột này được thu thập, validate, lưu DB nhưng không có bất kỳ nơi nào
    (route, service sinh lộ trình) đọc lại giá trị này, khác với study_days_per_week/
    study_minutes_per_day (2 trường cùng nhóm) vẫn được PersonalizedLearningPage.tsx tự điền vào
    form tạo lộ trình. Người dùng xác nhận xóa hẳn thay vì wire vào dùng.
    """
    # Lưu ý: op.drop_constraint tự áp dụng naming_convention (ck_%(table_name)s_%(constraint_name)s,
    # xem app/db/base.py) lên tên truyền vào — phải truyền tên LOGIC gốc ("session_minutes_range"),
    # KHÔNG phải tên đầy đủ đã có sẵn tiền tố "ck_student_profiles_", nếu không Alembic sẽ cộng dồn
    # tiền tố 2 lần và không tìm thấy constraint (đã xác nhận qua lỗi thực tế khi chạy migration).
    op.drop_constraint("session_minutes_range", "student_profiles", type_="check")
    op.drop_column("student_profiles", "preferred_session_minutes")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "student_profiles",
        sa.Column("preferred_session_minutes", sa.Integer(), nullable=False, server_default="30"),
    )
    op.create_check_constraint(
        "session_minutes_range",
        "student_profiles",
        "preferred_session_minutes >= 10 AND preferred_session_minutes <= 180",
    )
