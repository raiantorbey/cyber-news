import argparse
import asyncio
import sys

from app.config import get_settings
from app.database import SessionLocal
from app.ingestion import IngestionService
from app.models import RunStatus, SourceKind
from app.persistence import backfill_article_image_urls


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SignalWatch ingestion once")
    parser.add_argument("--source", choices=[kind.value for kind in SourceKind], action="append")
    parser.add_argument(
        "--backfill-images",
        action="store_true",
        help="Extract + cache article images, then exit",
    )
    args = parser.parse_args()
    settings = get_settings()
    if args.backfill_images:
        with SessionLocal() as session:
            updated = backfill_article_image_urls(session)
            session.commit()
        attached = asyncio.run(IngestionService(SessionLocal, settings)._fetch_missing_article_images(concurrency=1))
        print(f"image_urls_filled={updated} images_cached={attached}")
        return
    kinds = {SourceKind(value) for value in args.source} if args.source else None
    runs = asyncio.run(IngestionService(SessionLocal, settings).run(kinds))
    for run in runs:
        print(f"source={run.source_id} status={run.status.value} seen={run.items_seen} written={run.items_written}")
    if any(run.status != RunStatus.SUCCEEDED for run in runs):
        sys.exit(1)


if __name__ == "__main__":
    main()
