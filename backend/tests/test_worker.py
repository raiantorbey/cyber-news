import asyncio
from types import SimpleNamespace

import pytest

from app import worker
from app.models import SourceKind


@pytest.mark.asyncio
async def test_provider_schedules_run_independently(monkeypatch) -> None:
    nvd_release = asyncio.Event()
    rss_ran_twice = asyncio.Event()
    rss_runs = 0

    class FakeService:
        def __init__(self, *_):
            pass

        async def run(self, kinds):
            nonlocal rss_runs
            kind = next(iter(kinds))
            if kind == SourceKind.NVD:
                await nvd_release.wait()
            if kind == SourceKind.RSS:
                rss_runs += 1
                if rss_runs == 2:
                    rss_ran_twice.set()
            return []

    settings = SimpleNamespace(
        rss_interval_seconds=0.01,
        nvd_interval_seconds=60,
        cisa_interval_seconds=60,
        github_interval_seconds=60,
    )
    monkeypatch.setattr(worker, "get_settings", lambda: settings)
    monkeypatch.setattr(worker, "IngestionService", FakeService)
    task = asyncio.create_task(worker.worker_loop())
    try:
        await asyncio.wait_for(rss_ran_twice.wait(), timeout=1)
        assert not nvd_release.is_set()
    finally:
        nvd_release.set()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
