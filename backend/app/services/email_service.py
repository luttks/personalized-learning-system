"""Transactional email notifications for roadmap creation and daily study reminders."""
from __future__ import annotations

import asyncio
import html
import logging
import smtplib
from datetime import date, datetime
from email.message import EmailMessage
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


def email_is_configured() -> bool:
    return bool(settings.smtp_username and settings.smtp_password)


def _send(message: EmailMessage) -> None:
    with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.login(settings.smtp_username or "", settings.smtp_password or "")
        smtp.send_message(message)


async def send_email(to: str, subject: str, text: str, html_body: str) -> None:
    if not email_is_configured():
        logger.info("SMTP chưa cấu hình; bỏ qua email tới %s", to)
        return
    message = EmailMessage()
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_username}>"
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html_body, subtype="html")
    await asyncio.to_thread(_send, message)


def _date(value: Any) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(value or "")


def _roadmap_days(roadmap_data: dict[str, Any]) -> list[dict[str, Any]]:
    days: list[dict[str, Any]] = []
    for phase in roadmap_data.get("phases", []):
        for item in phase.get("days", []):
            days.append({**item, "phase_title": phase.get("title", "")})
    return sorted(days, key=lambda item: (str(item.get("date", "")), item.get("day_number", 0)))


async def send_roadmap_created_email(
    *, email: str, learner_name: str, course_name: str, roadmap: dict[str, Any], created_at: datetime
) -> None:
    phases = roadmap.get("phases", [])
    total_days = roadmap.get("total_days") or sum(len(p.get("days", [])) for p in phases)
    lines = [f"Chào {learner_name},", "", "Lộ trình học tập cá nhân hóa của bạn bằng AI đã được thiết lập thành công!", "", f"Khóa học: {course_name}", f"Ngày tạo: {created_at.strftime('%d/%m/%Y')}", f"Tổng thời lượng: {total_days} ngày học", "", "Tổng quan các giai đoạn:"]
    for index, phase in enumerate(phases, 1):
        days = phase.get("days", [])
        dates = [str(day.get("date")) for day in days if day.get("date")]
        span = f"{_date(min(dates))} → {_date(max(dates))}" if dates else ""
        minutes = sum(int(day.get("total_minutes", 0) or 0) for day in days)
        lines.append(f"{index}. {phase.get('title', 'Giai đoạn')} ({len(days)} ngày | ~{round(minutes / 60, 1)} giờ): {span}")
    lines.extend(["", "Bạn có thể theo dõi chi tiết và cập nhật tiến độ trực tiếp trên hệ thống.", f"Xem chi tiết lộ trình: {settings.app_base_url}/roadmap"])
    text = "\n".join(lines)
    subject = f"🎉 Tạo thành công lộ trình học tập: {course_name}"
    body = "<html><body>" + "<br>".join(html.escape(line) for line in lines) + f'<p><a href="{html.escape(settings.app_base_url)}/roadmap">Xem chi tiết lộ trình</a></p></body></html>'
    await send_email(email, subject, text, body)


async def send_daily_reminder_email(*, email: str, learner_name: str, course_name: str, roadmap: dict[str, Any], today: date) -> None:
    day = next((item for item in _roadmap_days(roadmap) if str(item.get("date", "")) == today.isoformat()), None)
    if not day:
        return
    topics = day.get("topics", [])
    total = int(day.get("total_minutes", 0) or 0)
    lines = [f"Chào {learner_name},", "", f"Hôm nay là ngày {day.get('day_number', '')} trong lộ trình học {course_name}.", f"Mục tiêu giai đoạn: {day.get('phase_title', '')}", "", f"Nhiệm vụ hôm nay (Tổng thời gian: {total} phút):"]
    for index, topic in enumerate(topics, 1):
        lines.extend([f"{index}. {topic.get('title', 'Chủ đề')} ({topic.get('minutes', 0)} phút)", f"   Mục đích: {topic.get('why', '')}", f"   Hoạt động: {topic.get('activities', '')}"])
    lines.extend(["", "🏁 Hãy hoàn thành các nhiệm vụ và kiểm tra nhanh cuối ngày.", f"Bắt đầu học ngay: {settings.app_base_url}/roadmap"])
    text = "\n".join(lines)
    subject = f"📚 Lịch học hôm nay (Ngày {day.get('day_number', '')}): {course_name}"
    body = "<html><body>" + "<br>".join(html.escape(line) for line in lines) + f'<p><a href="{html.escape(settings.app_base_url)}/roadmap">Bắt đầu học ngay</a></p></body></html>'
    await send_email(email, subject, text, body)


async def send_password_reset_email(*, email: str, learner_name: str, code: str) -> None:
    subject = "Mã xác nhận đổi mật khẩu - Personalized Learning System"
    text = f"Chào {learner_name},\n\nMã xác nhận đổi mật khẩu của bạn là: {code}\nMã có hiệu lực trong 10 phút và chỉ dùng một lần.\n\nNếu bạn không yêu cầu, hãy bỏ qua email này."
    body = f"<html><body><p>Chào {html.escape(learner_name)},</p><p>Mã xác nhận đổi mật khẩu:</p><h2>{code}</h2><p>Mã có hiệu lực trong 10 phút và chỉ dùng một lần.</p></body></html>"
    await send_email(email, subject, text, body)
