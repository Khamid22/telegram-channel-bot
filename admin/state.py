from __future__ import annotations

from apscheduler.schedulers.base import STATE_PAUSED, STATE_RUNNING, SchedulerNotRunningError

from core.generation_jobs import GenerationJobManager
from core.scheduler import build_scheduler

# Global scheduler instance shared across the process.
runtime_scheduler = None

# In-memory generation job registry.
generation_jobs = GenerationJobManager()


def scheduler_state() -> str:
    if not runtime_scheduler:
        return "stopped"
    if runtime_scheduler.state == STATE_RUNNING:
        return "running"
    if runtime_scheduler.state == STATE_PAUSED:
        return "paused"
    return "stopped"


def reload_scheduler() -> None:
    global runtime_scheduler
    _shutdown_scheduler()
    runtime_scheduler = build_scheduler()
    runtime_scheduler.start()


def ensure_scheduler_running():
    global runtime_scheduler
    if runtime_scheduler and runtime_scheduler.state in (STATE_RUNNING, STATE_PAUSED):
        return runtime_scheduler
    runtime_scheduler = build_scheduler()
    runtime_scheduler.start()
    return runtime_scheduler


def _shutdown_scheduler() -> None:
    global runtime_scheduler
    if not runtime_scheduler:
        return
    try:
        runtime_scheduler.shutdown(wait=False)
    except SchedulerNotRunningError:
        pass
    finally:
        runtime_scheduler = None
