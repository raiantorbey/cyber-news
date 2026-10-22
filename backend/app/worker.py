import asyncio
import logging
from time import monotonic

from app.config import get_settings
from app.database import SessionLocal
from app.ingestion import IngestionService
from app.models import SourceKind


async def worker_loop() -> None:
    settings = get_settings()
    service = IngestionService(SessionLocal, settings)
    intervals = {
        SourceKind.RSS: settings.rss_interval_seconds,
        SourceKind.NVD: settings.nvd_interval_seconds,
        SourceKind.CISA: settings.cisa_interval_seconds,
        SourceKind.GITHUB: settings.github_interval_seconds,
    }
    async def schedule(kind: SourceKind, interval: int) -> None:
        next_run = monotonic()
        while True:
            await asyncio.sleep(max(0.0, next_run - monotonic()))
            await service.run({kind})
            next_run = monotonic() + interval

    await asyncio.gather(*(schedule(kind, interval) for kind, interval in intervals.items()))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
