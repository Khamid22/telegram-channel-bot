from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from database.repositories import LogRepository, ScheduleRepository
from database.session import SessionLocal
from core.publishing import PublishingService

logger = logging.getLogger(__name__)

DAY_MAP = {
    "mon": "mon",
    "monday": "mon",
    "tue": "tue",
    "tuesday": "tue",
    "wed": "wed",
    "wednesday": "wed",
    "thu": "thu",
    "thursday": "thu",
    "fri": "fri",
    "friday": "fri",
    "sat": "sat",
    "saturday": "sat",
    "sun": "sun",
    "sunday": "sun",
}


def coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value).strip()] if str(value).strip() else []


def normalize_days(value: Any) -> list[str]:
    return [DAY_MAP.get(day.lower(), day.lower()) for day in coerce_list(value)]


def normalize_time(value: Any) -> str | None:
    text = str(value).strip()
    if not text:
        return None

    match = re.fullmatch(r"(\d{1,2}):(\d{1,2})", text)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
    elif re.fullmatch(r"\d{1,2}", text):
        hour, minute = int(text), 0
    elif re.fullmatch(r"\d{3,4}", text):
        hour, minute = int(text[:-2]), int(text[-2:])
    else:
        return None

    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


def normalize_times(value: Any) -> list[str]:
    normalized = []
    for item in coerce_list(value):
        publish_time = normalize_time(item)
        if publish_time:
            normalized.append(publish_time)
        else:
            logger.warning("Ignoring invalid schedule time: %s", item)
    return normalized


def publish_job(schedule_id: int | None = None) -> None:
    db = SessionLocal()
    try:
        LogRepository(db).add("scheduler_tick", f"Publish job started from schedule {schedule_id}")
        db.commit()
        asyncio.run(PublishingService(db).publish_next())
    except Exception as exc:
        logger.exception("Scheduled publish failed")
        LogRepository(db).add("scheduler_failed", str(exc), level="error", payload={"schedule_id": schedule_id})
        db.commit()
        raise
    finally:
        db.close()


def build_scheduler() -> BackgroundScheduler:
    db = SessionLocal()
    try:
        schedules = ScheduleRepository(db).active()
        scheduler = BackgroundScheduler()

        for schedule in schedules:
            if schedule.is_paused:
                continue

            days = ",".join(normalize_days(schedule.days)) or "*"
            times = normalize_times(schedule.times)
            for index, publish_time in enumerate(times):
                hour, minute = [int(part) for part in publish_time.split(":", 1)]
                trigger = CronTrigger(
                    day_of_week=days,
                    hour=hour,
                    minute=minute,
                    timezone=schedule.timezone,
                    jitter=schedule.random_interval_minutes * 60 if schedule.random_interval_minutes else None,
                )
                scheduler.add_job(
                    publish_job,
                    trigger=trigger,
                    id=f"schedule-{schedule.id}-{index}",
                    kwargs={"schedule_id": schedule.id},
                    replace_existing=True,
                    max_instances=1,
                    coalesce=True,
                )
        return scheduler
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    scheduler = build_scheduler()
    scheduler.start()
    logger.info("Scheduler started with %s jobs", len(scheduler.get_jobs()))
    return scheduler
