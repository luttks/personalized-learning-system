from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "personalized_learning",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Ho_Chi_Minh",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "send-daily-study-reminders": {
            "task": "reminders.send_daily_digest",
            "schedule": crontab(
                hour=settings.daily_reminder_email_hour,
                minute=settings.daily_reminder_email_minute,
            ),
        },
        # Buổi nhắc THỨ 2 trong ngày, RIÊNG cho người học đang bị khóa 1 giai đoạn để học lại — độc
        # lập hoàn toàn với digest bình thường ở trên (task khác, cột dedup khác
        # last_boost_reminder_sent_at), không đụng gì tới lịch 7h sáng hiện có.
        "send-stuck-learner-boost-reminders": {
            "task": "reminders.send_stuck_learner_boost",
            "schedule": crontab(
                hour=settings.stuck_reminder_email_hour,
                minute=settings.stuck_reminder_email_minute,
            ),
        },
    },
)