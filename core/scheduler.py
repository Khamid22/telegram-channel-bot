from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database.repositories import LogRepository, PostRepository
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


def publish_due_posts() -> None:
    db = SessionLocal()
    try:
        due_posts = PostRepository(db).due(datetime.now(timezone.utc))
        if not due_posts:
            return
        logs = LogRepository(db)
        publisher = PublishingService(db)
        for post in due_posts:
            logs.add("scheduler_tick", f"Publishing scheduled post {post.id}", payload={"post_id": post.id})
            db.commit()
            asyncio.run(publisher.publish(post))
    except Exception as exc:
        logger.exception("Scheduled publish failed")
        db.rollback()
        LogRepository(db).add("scheduler_failed", str(exc), level="error")
        db.commit()
        raise
    finally:
        db.close()


def build_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        publish_due_posts,
        trigger=IntervalTrigger(minutes=1),
        id="publish-due-posts",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    return scheduler


def start_scheduler() -> BackgroundScheduler:
    scheduler = build_scheduler()
    scheduler.start()
    logger.info("Scheduler started with %s jobs", len(scheduler.get_jobs()))
    return scheduler
