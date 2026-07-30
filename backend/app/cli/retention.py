import argparse
import json

from app.core.config import get_settings
from app.db.session import Database
from app.modules.operations.retention import redact_expired_provider_payloads


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report or redact expired TikHub response payloads."
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply redaction. The default is a dry run.",
    )
    parser.add_argument(
        "--confirm-redact-provider-payloads",
        action="store_true",
        help="Required together with --execute.",
    )
    args = parser.parse_args()
    if args.execute and not args.confirm_redact_provider_payloads:
        parser.error("--execute requires --confirm-redact-provider-payloads")

    settings = get_settings()
    database = Database(settings.database_url)
    try:
        with database.session_factory() as db:
            result = redact_expired_provider_payloads(
                db,
                successful_retention_days=settings.provider_payload_retention_days,
                failed_retention_days=settings.failed_provider_payload_retention_days,
                execute=args.execute,
            )
    finally:
        database.dispose()
    print(
        json.dumps(
            {
                "mode": "execute" if args.execute else "dry-run",
                "eligible_payloads": result.eligible_payloads,
                "redacted_payloads": result.redacted_payloads,
            }
        )
    )


if __name__ == "__main__":
    main()
