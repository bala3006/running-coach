from contextlib import AsyncExitStack

import pytest

from running_coach.mcp_host import connect_mcp_servers


@pytest.mark.asyncio
async def test_host_discovers_only_the_expected_read_tools() -> None:
    async with AsyncExitStack() as stack:
        clients, tools = await connect_mcp_servers(stack)

    assert set(clients) == {"strava", "sheets"}
    assert {tool["function"]["name"] for tool in tools} == {
        "strava_recent_runs",
        "sheets_training_sheet",
    }
