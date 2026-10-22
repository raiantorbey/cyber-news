from types import SimpleNamespace

import pytest

from app import cli
from app.models import RunStatus


def test_cli_reports_all_runs_and_exits_nonzero_on_failure(monkeypatch, capsys) -> None:
    runs = [
        SimpleNamespace(source_id=1, status=RunStatus.SUCCEEDED, items_seen=2, items_written=1),
        SimpleNamespace(source_id=2, status=RunStatus.FAILED, items_seen=0, items_written=0),
    ]

    class FakeService:
        def __init__(self, *_):
            pass

        async def run(self, _):
            return runs

    monkeypatch.setattr(cli, "IngestionService", FakeService)
    monkeypatch.setattr("sys.argv", ["signalwatch-ingest", "--source", "rss"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "source=1 status=succeeded" in output
    assert "source=2 status=failed" in output
