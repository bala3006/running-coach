import json

from mcp.server import MCPServer

from running_coach.integrations import get_training_sheet

server = MCPServer("running-coach-sheets", instructions="Read-only access to the configured Google training Sheet.")


@server.tool(description="Read the configured Google Sheets training profile or plan. Read-only.")
async def training_sheet() -> str:
    """Return rows from the read-only range configured by GOOGLE_SHEET_ID and GOOGLE_SHEET_RANGE."""
    try:
        sheet = await get_training_sheet()
        return json.dumps(sheet, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


if __name__ == "__main__":
    server.run(transport="stdio")
