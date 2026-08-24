"""Gửi email qua SMTP chuẩn (smtplib). Nếu chưa cấu hình SMTP_HOST trong .env, không gửi email
thật mà chỉ ghi mã OTP ra log — để môi trường dev/test local vẫn đi hết được luồng xác thực mà
không cần tài khoản SMTP thật."""
from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send_email_sync(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    message = EmailMessage()
    from_name = settings.smtp_from_name
    from_email = settings.smtp_from_email or settings.smtp_user
    message["Subject"] = subject
    message["From"] = f"{from_name} <{from_email}>"
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_user and settings.smtp_password:
            server.login(settings.smtp_user, settings.smtp_password)
        server.send_message(message)


async def send_otp_email(to_email: str, full_name: str, code: str) -> None:
    """Gửi mã OTP 6 chữ số xác thực đăng ký. Không raise ra ngoài khi gửi thất bại — đăng ký
    vẫn thành công, người dùng có thể bấm "Gửi lại mã" nếu không nhận được email."""
    subject = "Mã xác thực đăng ký - Personalized Learning System"
    text_body = (
        f"Chào {full_name},\n\n"
        f"Mã xác thực email của bạn là: {code}\n"
        f"Mã có hiệu lực trong {settings.otp_expire_minutes} phút.\n\n"
        "Nếu bạn không thực hiện đăng ký này, vui lòng bỏ qua email."
    )
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;">
      <h2 style="color:#0f766e;">Xác thực địa chỉ email</h2>
      <p>Chào <b>{full_name}</b>,</p>
      <p>Mã xác thực đăng ký tài khoản của bạn là:</p>
      <p style="font-size:32px;font-weight:bold;letter-spacing:8px;color:#0f766e;">{code}</p>
      <p>Mã có hiệu lực trong <b>{settings.otp_expire_minutes} phút</b>.</p>
      <p style="color:#64748b;font-size:13px;">Nếu bạn không thực hiện đăng ký này, vui lòng bỏ qua email.</p>
    </div>
    """

    if not settings.smtp_host:
        logger.warning(
            f"[DEV] SMTP chưa cấu hình — mã OTP cho {to_email}: {code} "
            f"(hết hạn sau {settings.otp_expire_minutes} phút)"
        )
        return

    try:
        await asyncio.to_thread(_send_email_sync, to_email, subject, html_body, text_body)
    except Exception as error:
        logger.error(f"Gửi email OTP tới {to_email} thất bại: {error}")


async def send_daily_reminder_digest(to_email: str, full_name: str, items: list[dict]) -> None:
    """Gửi MỘT email/người/ngày nhắc học, gộp mọi lộ trình đã "áp dụng" có lịch học hôm nay —
    tránh spam nhiều email nếu người dùng học song song nhiều môn. `items`:
    [{"roadmap_title", "phase_title", "topics": [str], "total_minutes", "assessment_ready": bool}]
    Không raise ra ngoài khi gửi thất bại — task Celery vẫn coi là đã xử lý xong ngày hôm đó."""
    subject = "Nhắc học hôm nay - Personalized Learning System"

    text_sections = []
    html_sections = []
    for item in items:
        topics_line = ", ".join(item.get("topics", [])) or "Ôn tập"
        text_sections.append(
            f"- {item['roadmap_title']} — {item['phase_title']} ({item.get('total_minutes', 0)} phút)\n"
            f"  Nội dung: {topics_line}"
            + ("\n  Bạn có bài kiểm tra cuối giai đoạn đang chờ làm!" if item.get("assessment_ready") else "")
        )
        html_sections.append(f"""
        <li style="margin-bottom:12px;">
          <b>{item['roadmap_title']}</b> — {item['phase_title']} ({item.get('total_minutes', 0)} phút)<br/>
          <span style="color:#475569;">Nội dung: {topics_line}</span>
          {"<br/><span style='color:#b45309;'>⚠ Bạn có bài kiểm tra cuối giai đoạn đang chờ làm!</span>" if item.get("assessment_ready") else ""}
        </li>
        """)

    text_body = (
        f"Chào {full_name},\n\n"
        f"Đây là lịch học hôm nay của bạn:\n\n" + "\n\n".join(text_sections) +
        "\n\nHãy đăng nhập để tiếp tục lộ trình nhé!"
    )
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;">
      <h2 style="color:#0f766e;">Lịch học hôm nay</h2>
      <p>Chào <b>{full_name}</b>, đây là lịch học hôm nay của bạn:</p>
      <ul style="padding-left:18px;">{"".join(html_sections)}</ul>
      <p style="color:#64748b;font-size:13px;">Hãy đăng nhập để tiếp tục lộ trình nhé!</p>
    </div>
    """

    if not settings.smtp_host:
        logger.warning(f"[DEV] SMTP chưa cấu hình — digest nhắc học cho {to_email}:\n{text_body}")
        return

    try:
        await asyncio.to_thread(_send_email_sync, to_email, subject, html_body, text_body)
    except Exception as error:
        logger.error(f"Gửi email nhắc học tới {to_email} thất bại: {error}")


async def send_stuck_learner_reminder(to_email: str, full_name: str, items: list[dict]) -> None:
    """Email nhắc nhở BUỔI 2 trong ngày, RIÊNG cho người học đang bị khóa 1 giai đoạn để học lại
    (status='locked_for_retry') — nội dung khác hẳn digest thường (không phải "lịch hôm nay", mà là
    cảnh báo hổng kiến thức + ngày sẽ mở khóa lại). `items`:
    [{"roadmap_title", "phase_title", "retry_unlock_at": str | None}]. Không raise ra ngoài khi gửi
    thất bại — task Celery vẫn coi là đã xử lý xong (đánh dấu qua last_boost_reminder_sent_at)."""
    subject = "Bạn đang bị hổng kiến thức — cần học lại - Personalized Learning System"

    text_sections = []
    html_sections = []
    for item in items:
        unlock_line = (
            f"Bài kiểm tra sẽ mở lại vào {item['retry_unlock_at']}."
            if item.get("retry_unlock_at") else "Bài kiểm tra sẽ mở lại sau khi bạn học đủ thời gian."
        )
        text_sections.append(f"- {item['roadmap_title']} — {item['phase_title']}: {unlock_line}")
        html_sections.append(
            f"<li style='margin-bottom:12px;'><b>{item['roadmap_title']}</b> — {item['phase_title']}<br/>"
            f"<span style='color:#b45309;'>{unlock_line}</span></li>"
        )

    text_body = (
        f"Chào {full_name},\n\n"
        "Bạn đã bỏ qua một giai đoạn đang hổng kiến thức và làm bài kiểm tra chưa đạt — hệ thống đã "
        "tạm khóa giai đoạn tiếp theo để bạn có thời gian học lại chắc chắn hơn:\n\n"
        + "\n".join(text_sections) +
        "\n\nHãy tranh thủ ôn lại trước khi bài kiểm tra mở lại nhé!"
    )
    html_body = f"""
    <div style="font-family:Arial,sans-serif;max-width:520px;margin:0 auto;">
      <h2 style="color:#b45309;">Cần học lại trước khi tiếp tục</h2>
      <p>Chào <b>{full_name}</b>, bạn đã bỏ qua một giai đoạn đang hổng kiến thức và làm bài kiểm tra
      chưa đạt — hệ thống đã tạm khóa giai đoạn tiếp theo để bạn có thời gian học lại chắc chắn hơn:</p>
      <ul style="padding-left:18px;">{"".join(html_sections)}</ul>
      <p style="color:#64748b;font-size:13px;">Hãy tranh thủ ôn lại trước khi bài kiểm tra mở lại nhé!</p>
    </div>
    """

    if not settings.smtp_host:
        logger.warning(f"[DEV] SMTP chưa cấu hình — nhắc nhở học lại cho {to_email}:\n{text_body}")
        return

    try:
        await asyncio.to_thread(_send_email_sync, to_email, subject, html_body, text_body)
    except Exception as error:
        logger.error(f"Gửi email nhắc học lại tới {to_email} thất bại: {error}")
