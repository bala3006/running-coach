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


@pytest.mark.asyncio
async def test_training_sheet_marks_light_blue_rows_completed(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet-id")
    monkeypatch.setenv("GOOGLE_SHEET_RANGE", "Marathon!A1:B3")

    async def fake_token(provider):
        assert provider == "google"
        return {"access_token": "test-token"}

    blue = {"red": 0.6431373, "green": 0.7607843, "blue": 0.95686275}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "sheets": [
                    {
                        "properties": {"title": "Marathon"},
                        "data": [
                            {
                                "startRow": 0,
                                "rowData": [
                                    {"values": [{"formattedValue": "Date"}, {"formattedValue": "Run"}]},
                                    {"values": [{"formattedValue": "Oct 1"}, {"formattedValue": "Long run", "effectiveFormat": {"backgroundColor": blue}}]},
                                    {"values": [{"formattedValue": "Oct 3"}, {"formattedValue": "Easy run"}]},
                                ],
                            }
                        ],
                    }
                ]
            }

    class FakeClient:
        def __init__(self, timeout):
            assert timeout == 20

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers, params):
            assert url.endswith("/spreadsheets/sheet-id")
            assert headers["Authorization"] == "Bearer test-token"
            assert params["ranges"] == "Marathon!A1:B3"
            assert params["includeGridData"] == "true"
            assert "effectiveFormat(backgroundColor)" in params["fields"]
            return FakeResponse()

    monkeypatch.setattr(integrations, "_service_token", fake_token)
    monkeypatch.setattr(integrations.httpx, "AsyncClient", FakeClient)

    sheet = await integrations.get_training_sheet()

    assert sheet["sheet"] == "Marathon"
    assert sheet["completed_count"] == 1
    assert sheet["rows"][1] == {
        "row_number": 2,
        "values": ["Oct 1", "Long run"],
        "completed": True,
    }
    assert sheet["rows"][2]["completed"] is False


@pytest.mark.asyncio
async def test_run_descent_is_summed_from_strava_altitude_stream(monkeypatch) -> None:
    async def fake_token(provider):
        assert provider == "strava"
        return {"access_token": "test-token"}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"altitude": {"data": [100, 120, 110, 130, 115]}}

    class FakeClient:
        def __init__(self, timeout):
            assert timeout == 20

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, headers, params):
            assert url.endswith("/activities/42/streams")
            assert headers["Authorization"] == "Bearer test-token"
            assert params == {"keys": "altitude", "key_by_type": "true"}
            return FakeResponse()

    monkeypatch.setattr(integrations, "_service_token", fake_token)
    monkeypatch.setattr(integrations.httpx, "AsyncClient", FakeClient)

    assert await integrations.get_run_descent("42") == 25
