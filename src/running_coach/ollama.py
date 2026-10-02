import os
from contextlib import AsyncExitStack

import httpx

from running_coach.mcp_host import call_mcp_tool, connect_mcp_servers
from running_coach.prompts import build_system_prompt
from running_coach.response_safety import remove_unverified_research
from running_coach.voice import add_english_tamil_touch


async def chat_with_ollama(
    message: str,
    language: str,
    tamil_voice: bool,
    history: list[dict[str, str]] | None = None,
) -> str:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = os.getenv("OLLAMA_MODEL", "qwen3:8b")
    messages = [{"role": "system", "content": build_system_prompt(language, tamil_voice)}]
    messages.extend(history or [])
    messages.append({"role": "user", "content": message})

    async with AsyncExitStack() as stack:
        clients, tools = await connect_mcp_servers(stack)
        async with httpx.AsyncClient(timeout=120) as client:
            for _ in range(4):
                response = await client.post(
                    f"{base_url}/api/chat",
                    json={"model": model, "stream": False, "messages": messages, "tools": tools},
                )
                response.raise_for_status()
                assistant = response.json().get("message", {})
                messages.append(assistant)
                tool_calls = assistant.get("tool_calls", [])
                if not tool_calls:
                    content = assistant.get("content", "").strip()
                    if not content:
                        raise RuntimeError("Ollama returned an empty response")
                    content = remove_unverified_research(content)
                    if language == "en-ta":
                        content = add_english_tamil_touch(content)
                    return content
                for tool_call in tool_calls:
                    function = tool_call.get("function", {})
                    result = await call_mcp_tool(
                        clients,
                        function.get("name", ""),
                        function.get("arguments", {}),
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": function.get("name", ""),
                            "content": result,
                        }
                    )
    raise RuntimeError("Ollama exceeded the maximum tool-call rounds")
