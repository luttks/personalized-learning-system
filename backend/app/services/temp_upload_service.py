"""Lưu trữ tạm file trong lúc người dùng đang thao tác luồng "Lộ trình học".

Vấn đề: file gốc (đối tượng File ở trình duyệt) không thể lưu lại qua sessionStorage khi người
dùng chuyển sang trang khác rồi quay lại — nên trước đây phải bắt người dùng chọn lại file.

Giải pháp: ngay khi phân tích tài liệu (bước đầu tiên), file được lưu tạm vào
`uploads/_tmp/{user_id}/{temp_id}/` và trả về `temp_file_id` (một chuỗi ngắn, lưu được bình
thường trong sessionStorage). Khi nộp bài cuối cùng, hệ thống đọc lại file từ đây, lưu chính thức
vào `uploads/{user_id}/...` (qua `save_upload_file`), rồi xóa bản tạm. Nếu người dùng bỏ dở giữa
chừng, bản tạm được dọn khi họ bấm "bắt đầu môn mới" hoặc bởi `sweep_stale_temp_files` (an toàn
cho trường hợp đóng tab mà không có hành động rõ ràng nào).
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import time
import uuid

logger = logging.getLogger(__name__)

TEMP_BASE_DIR = "uploads/_tmp"
TEMP_MAX_AGE_SECONDS = 24 * 3600

_TEMP_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def _validate_temp_id(temp_file_id: str) -> str:
    if not _TEMP_ID_PATTERN.fullmatch(temp_file_id or ""):
        raise ValueError("temp_file_id không hợp lệ")
    return temp_file_id


def _safe_filename(filename: str) -> str:
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)
    return name.strip(". ")[:150] or "upload"


def _temp_dir(user_id: str, temp_file_id: str) -> str:
    return os.path.join(TEMP_BASE_DIR, str(user_id), _validate_temp_id(temp_file_id))


def save_temp_file(file_bytes: bytes, filename: str, user_id: str) -> str:
    """Lưu file vào thư mục tạm, trả về temp_file_id để tham chiếu lại sau."""
    temp_id = uuid.uuid4().hex
    dir_path = os.path.join(TEMP_BASE_DIR, str(user_id), temp_id)
    os.makedirs(dir_path, exist_ok=True)
    target = os.path.join(dir_path, _safe_filename(filename))
    with open(target, "wb") as f:
        f.write(file_bytes)
    return temp_id


def read_temp_file(temp_file_id: str, user_id: str) -> tuple[bytes, str] | None:
    """Đọc lại (bytes, filename) đã lưu tạm; None nếu không tìm thấy hoặc đã bị dọn."""
    try:
        dir_path = _temp_dir(user_id, temp_file_id)
    except ValueError:
        return None
    if not os.path.isdir(dir_path):
        return None
    entries = [e for e in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, e))]
    if not entries:
        return None
    filename = entries[0]
    with open(os.path.join(dir_path, filename), "rb") as f:
        return f.read(), filename


def discard_temp_file(temp_file_id: str, user_id: str) -> None:
    """Xóa file tạm — gọi sau khi đã lưu chính thức, hoặc khi người dùng bỏ dở."""
    try:
        dir_path = _temp_dir(user_id, temp_file_id)
    except ValueError:
        return
    shutil.rmtree(dir_path, ignore_errors=True)


def sweep_stale_temp_files(
    base_dir: str = TEMP_BASE_DIR, max_age_seconds: int = TEMP_MAX_AGE_SECONDS
) -> int:
    """Dọn các file tạm quá hạn (phòng khi người dùng đóng tab mà không thao tác gì thêm).
    Trả về số thư mục đã xóa."""
    if not os.path.isdir(base_dir):
        return 0
    removed = 0
    now = time.time()
    for user_dir in os.scandir(base_dir):
        if not user_dir.is_dir():
            continue
        for temp_dir in os.scandir(user_dir.path):
            if not temp_dir.is_dir():
                continue
            try:
                if now - temp_dir.stat().st_mtime > max_age_seconds:
                    shutil.rmtree(temp_dir.path, ignore_errors=True)
                    removed += 1
            except OSError as e:
                logger.warning(f"Sweep temp file lỗi tại '{temp_dir.path}': {e}")
    return removed
