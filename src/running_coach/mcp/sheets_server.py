import json

from mcp.server import MCPServer

from running_coach.integrations import get_training_sheet

server = MCPServer(
    "running-coach-sheets",
    instructions="Read-only access to the configured Google training Sheet, including light-blue completed-row status.",
)


@server.tool(description="Read the configured Google Sheets training profile or plan. Rows with light-blue cells are marked completed. Read-only.")
async def training_sheet() -> str:
    """Return row values and light-blue completion status from the configured read-only range."""
    try:
        sheet = await get_training_sheet()
        return json.dumps(sheet, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


if __name__ == "__main__":
    server.run(transport="stdio")
