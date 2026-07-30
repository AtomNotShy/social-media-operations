import argparse
import asyncio
import os
import socket

from app.core.config import Settings, get_settings
from app.db.session import Database
from app.jobs.service import schedule_due_profile_scans, touch_process_heartbeat


async def run_scheduler(settings: Settings, *, once: bool = False) -> None:
    database = Database(settings.database_url)
    instance_id = f"{socket.gethostname()}:{os.getpid()}:scheduler"
    try:
        while True:
            with database.session_factory() as db:
                touch_process_heartbeat(
                    db,
                    instance_id=instance_id,
                    service="scheduler",
                )
                schedule_due_profile_scans(db)
                db.commit()
            if once:
                return
            await asyncio.sleep(settings.scheduler_poll_seconds)
    finally:
        database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Schedule due social profile scans")
    parser.add_argument("--once", action="store_true", help="Schedule one due batch")
    args = parser.parse_args()
    asyncio.run(run_scheduler(get_settings(), once=args.once))


if __name__ == "__main__":
    main()
