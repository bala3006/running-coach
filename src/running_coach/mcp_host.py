import os
import sys
from contextlib import AsyncExitStack

from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER_MODULES = {
    "strava": "running_coach.mcp.strava_server",
    "sheets": "running_coach.mcp.sheets_server",
}


async def connect_mcp_servers(stack: AsyncExitStack) -> tuple[dict[str, Client], list[dict]]:
    clients: dict[str, Client] = {}
    ollama_tools: list[dict] = []
    for label, module in SERVER_MODULES.items():
        params = StdioServerParameters(command=sys.executable, args=["-m", module], env=os.environ.copy())
        client = await stack.enter_async_context(Client(stdio_client(params)))
        clients[label] = client
        result = await client.list_tools()
        for tool in result.tools:
            ollama_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": f"{label}_{tool.name}",
                        "description": tool.description or "",
                        "parameters": tool.input_schema,
                    },
                }
            )
    return clients, ollama_tools


async def call_mcp_tool(clients: dict[str, Client], name: str, arguments: dict) -> str:
    label, tool_name = name.split("_", 1)
    if label not in clients:
        raise ValueError("The requested integration tool is not available")
    result = await clients[label].call_tool(tool_name, arguments)
    text = [block.text for block in result.content if hasattr(block, "text")]
    return "\n".join(text) or "The integration returned no text."
