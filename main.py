from __future__ import annotations

import argparse
import asyncio
import time

from admin.app import create_app
from bot.runner import run_bot
from config.logging import configure_logging
from config.settings import get_settings
from database.init_db import bootstrap_database
from core.scheduler import start_scheduler


def run_admin(with_scheduler: bool | None = None) -> None:
    settings = get_settings()
    bootstrap_database()
    start_background_scheduler = settings.start_scheduler_with_admin if with_scheduler is None else with_scheduler
    app = create_app(start_background_scheduler=start_background_scheduler)
    app.run(host=settings.admin_host, port=settings.bind_port)


def run_scheduler_forever() -> None:
    scheduler = start_scheduler()
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        scheduler.shutdown()


def main() -> None:
    configure_logging()
    parser = argparse.ArgumentParser(description="Multilevel Essays Telegram publisher")
    parser.add_argument(
        "command",
        choices=["init-db", "admin", "scheduler", "bot", "all"],
        help="Process to run",
    )
    args = parser.parse_args()

    if args.command == "init-db":
        bootstrap_database()
        print("Database initialized")
    elif args.command == "admin":
        run_admin()
    elif args.command == "scheduler":
        run_scheduler_forever()
    elif args.command == "bot":
        asyncio.run(run_bot())
    elif args.command == "all":
        bootstrap_database()
        run_admin(with_scheduler=True)
if __name__ == "__main__":
    main()
