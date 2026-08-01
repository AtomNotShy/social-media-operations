import argparse
import json

from app.core.config import get_settings
from app.db.session import Database
from app.modules.operations.retention import (
    delete_expired_unpromoted_contents,
    redact_expired_provider_payloads,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report or apply configured provider and content retention policies."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply explicitly confirmed actions. The default is a dry run.",
    )
    parser.add_argument(
        "--confirm-redact-provider-payloads",
        action="store_true",
        help="Required together with --execute.",
    )
    parser.add_argument(
        "--delete-expired-unpromoted-content",
        action="store_true",
        help="Include expired collected-content candidates in the report or execution.",
    )
    parser.add_argument(
        "--confirm-delete-expired-unpromoted-content",
        action="store_true",
        help="Required with --execute --delete-expired-unpromoted-content.",
    )
    args = parser.parse_args()
    if (
        args.execute
        and args.delete_expired_unpromoted_content
        and not args.confirm_delete_expired_unpromoted_content
    ):
        parser.error(
            "--execute --delete-expired-unpromoted-content requires "
            "--confirm-delete-expired-unpromoted-content"
        )
    if args.execute and not (
        args.confirm_redact_provider_payloads
        or args.confirm_delete_expired_unpromoted_content
    ):
        parser.error(
            "--execute requires --confirm-redact-provider-payloads or "
            "--confirm-delete-expired-unpromoted-content"
        )
    if (
        args.confirm_delete_expired_unpromoted_content
        and not args.delete_expired_unpromoted_content
    ):
        parser.error(
            "--confirm-delete-expired-unpromoted-content requires "
            "--delete-expired-unpromoted-content"
        )

    settings = get_settings()
    database = Database(settings.database_url)
    try:
        with database.session_factory() as db:
            result = redact_expired_provider_payloads(
                db,
                successful_retention_days=settings.provider_payload_retention_days,
                failed_retention_days=settings.failed_provider_payload_retention_days,
                execute=args.execute and args.confirm_redact_provider_payloads,
            )
            content_result = (
                delete_expired_unpromoted_contents(
                    db,
                    retention_days=settings.unpromoted_content_retention_days,
                    execute=(
                        args.execute and args.confirm_delete_expired_unpromoted_content
                    ),
                )
                if args.delete_expired_unpromoted_content
                else None
            )
    finally:
        database.dispose()
    print(
        json.dumps(
            {
                "mode": "execute" if args.execute else "dry-run",
                "eligible_payloads": result.eligible_payloads,
                "redacted_payloads": result.redacted_payloads,
                "eligible_contents": (
                    content_result.eligible_contents if content_result is not None else 0
                ),
                "deleted_contents": (
                    content_result.deleted_contents if content_result is not None else 0
                ),
            }
        )
    )


if __name__ == "__main__":
    main()
