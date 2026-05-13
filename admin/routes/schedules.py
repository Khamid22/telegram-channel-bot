from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from flask import Blueprint, request
from flask_login import login_required

from admin.serializers import schedule_payload
from admin.state import ensure_scheduler_running, reload_scheduler, scheduler_state
from admin.utils import _json
from apscheduler.schedulers.base import STATE_PAUSED
from config.settings import get_settings
from database.models import Schedule
from database.repositories import GenerationBatchRepository, PostRepository, ScheduleRepository
from database.session import SessionLocal
from core.scheduler import normalize_time, normalize_times

bp = Blueprint("schedules", __name__)


def _parse_schedule_data(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize raw request data into a schedule dict."""
    if not data.get("batch_id"):
        raise ValueError("Select a generated vocabulary batch.")

    start_date = date.fromisoformat(data["start_date"])
    end_date = date.fromisoformat(data["end_date"])
    if end_date < start_date:
        raise ValueError("End date must be on or after the start date.")

    settings = get_settings()
    dispatch_mode = data.get("dispatch_mode") or "even"
    manual_times = normalize_times(data.get("manual_times") or [])
    window_start = normalize_time(data.get("window_start") or "09:00")
    window_end = normalize_time(data.get("window_end") or "18:00")
    posts_per_day = int(data.get("posts_per_day") or 1)

    if posts_per_day < 1:
        raise ValueError("Posts per day must be at least 1.")

    if dispatch_mode == "manual":
        if not manual_times:
            raise ValueError("Manual scheduling requires at least one time.")
        posts_per_day = len(manual_times)
    else:
        start_m = int(window_start[:2]) * 60 + int(window_start[3:])
        end_m = int(window_end[:2]) * 60 + int(window_end[3:])
        if end_m < start_m:
            raise ValueError("The time window end must be after the start.")

    return {
        "name": data.get("name"),
        "content_type": "vocabulary",
        "batch_id": int(data["batch_id"]),
        "timezone": data.get("timezone") or settings.timezone,
        "start_date": start_date,
        "end_date": end_date,
        "dispatch_mode": dispatch_mode,
        "window_start": window_start,
        "window_end": window_end,
        "manual_times": manual_times,
        "posts_per_day": posts_per_day,
        "is_active": bool(data.get("is_active", True)),
        "is_paused": bool(data.get("is_paused", False)),
    }


def _times_for_schedule(sd: dict[str, Any]) -> list[str]:
    if sd["dispatch_mode"] == "manual":
        return sd["manual_times"]
    posts = sd["posts_per_day"]
    start_m = int(sd["window_start"][:2]) * 60 + int(sd["window_start"][3:])
    end_m = int(sd["window_end"][:2]) * 60 + int(sd["window_end"][3:])
    if posts == 1:
        return [sd["window_start"]]
    step = (end_m - start_m) / (posts - 1)
    return [f"{round(start_m + step * i) // 60:02d}:{round(start_m + step * i) % 60:02d}" for i in range(posts)]


def _schedule_slots(sd: dict[str, Any]) -> list[datetime]:
    zone = ZoneInfo(sd["timezone"])
    slots: list[datetime] = []
    current_day = sd["start_date"]
    while current_day <= sd["end_date"]:
        for t in _times_for_schedule(sd):
            h, m = int(t[:2]), int(t[3:])
            slots.append(datetime.combine(current_day, time(h, m), tzinfo=zone))
        current_day += timedelta(days=1)
    return slots


@bp.get("/api/schedules")
@login_required
def list_schedules():
    db = SessionLocal()
    try:
        return _json({"items": [schedule_payload(s) for s in ScheduleRepository(db).list()]})
    finally:
        db.close()


@bp.post("/api/schedules")
@login_required
def create_schedule():
    data = request.get_json(force=True)
    db = SessionLocal()
    try:
        sd = _parse_schedule_data(data)
        batch = GenerationBatchRepository(db).get(sd["batch_id"])
        if not batch or batch.status != "ready":
            return _json({"error": "Select a ready generated batch."}, 400)
        slots = _schedule_slots(sd)
        posts = PostRepository(db).unscheduled_for_batch(batch.id, limit=len(slots))
        if not posts:
            return _json({"error": "This batch has no unscheduled posts left."}, 400)
        schedule = Schedule(
            name=sd["name"],
            content_type=sd["content_type"],
            batch=batch,
            timezone=sd["timezone"],
            start_date=sd["start_date"],
            end_date=sd["end_date"],
            dispatch_mode=sd["dispatch_mode"],
            window_start=sd["window_start"],
            window_end=sd["window_end"],
            manual_times=sd["manual_times"],
            posts_per_day=sd["posts_per_day"],
            is_active=sd["is_active"],
            is_paused=sd["is_paused"],
        )
        db.add(schedule)
        db.flush()
        for post, scheduled_at in zip(posts, slots):
            post.schedule = schedule
            post.scheduled_at = scheduled_at
        schedule.scheduled_post_count = len(posts)
        db.commit()
        reload_scheduler()
        return _json({"item": schedule_payload(schedule)}, 201)
    except (RuntimeError, ValueError) as exc:
        db.rollback()
        return _json({"error": str(exc)}, 400)
    finally:
        db.close()


@bp.patch("/api/schedules/<int:schedule_id>")
@login_required
def update_schedule(schedule_id: int):
    data = request.get_json(force=True)
    db = SessionLocal()
    try:
        schedule = db.get(Schedule, schedule_id)
        if not schedule:
            return _json({"error": "Schedule not found"}, 404)
        for field in ("name", "is_active", "is_paused"):
            if field in data:
                setattr(schedule, field, data[field])
        db.commit()
        reload_scheduler()
        return _json({"item": schedule_payload(schedule)})
    finally:
        db.close()


@bp.delete("/api/schedules/<int:schedule_id>")
@login_required
def delete_schedule(schedule_id: int):
    db = SessionLocal()
    try:
        schedule = db.get(Schedule, schedule_id)
        if not schedule:
            return _json({"error": "Schedule not found"}, 404)
        for post in schedule.posts:
            if post.published_at is None:
                post.schedule = None
                post.scheduled_at = None
        db.delete(schedule)
        db.commit()
        reload_scheduler()
        return _json({"ok": True})
    finally:
        db.close()


@bp.post("/api/scheduler/pause")
@login_required
def pause_scheduler():
    s = ensure_scheduler_running()
    if s.state != STATE_PAUSED:
        s.pause()
    return _json({"paused": True, "state": scheduler_state()})


@bp.post("/api/scheduler/resume")
@login_required
def resume_scheduler():
    s = ensure_scheduler_running()
    if s.state == STATE_PAUSED:
        s.resume()
    return _json({"paused": False, "state": scheduler_state()})
