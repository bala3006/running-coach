import pytest

from running_coach import integrations


@pytest.mark.asyncio
async def test_recent_runs_rejects_unbounded_ranges() -> None:
    with pytest.raises(ValueError, match="between 1 and 90"):
        await integrations.get_recent_runs(120)


@pytest.mark.asyncio
async def test_training_sheet_requires_a_sheet_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)

    with pytest.raises(RuntimeError, match="GOOGLE_SHEET_ID"):
        await integrations.get_training_sheet()
