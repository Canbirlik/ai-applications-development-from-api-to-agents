import asyncio
import json
import os
import socket
from urllib.parse import urlparse

from commons.constants import OPENAI_API_KEY
from commons.models.message import Message
from commons.models.role import Role
from t10_mcp_advanced.agent.agent import CustomAgentMCP
from t10_mcp_advanced.agent.clients.custom_mcp_client import CustomMCPClient
from t10_mcp_advanced.agent.clients.mcp_client import MCPClient


async def main():
    #TODO:
    # 1. Take a look what applies CustomAgentMCP
    # 2. Create empty list where you save tools from MCP Servers later
    # 3. Create empty dict where where key is str (tool name) and value is instance of MCPClient or CustomMCPClient
    # 4. Create UMS MCPClient, url is `http://localhost:8006/mcp` (use static method create and don't forget that its async)
    # 5. Collect tools and dict [tool name, mcp client]
    # 6. Do steps 4 and 5 for `https://remote.mcpservers.org/fetch/mcp`
    # 7. Create CustomAgentMCP
    # 8. Create array with Messages and add there System message with simple instructions for LLM that it should help to handle user request
    # 9. Create simple console chat (as we done in previous tasks)
    tools: list[dict] = []
    tool_name_client_map: dict[str, MCPClient | CustomMCPClient] = {}

    ums_client = await CustomMCPClient.create("http://localhost:8006/mcp")
    ums_tools = await ums_client.get_tools()
    tools.extend(ums_tools)
    for tool in ums_tools:
        tool_name_client_map[tool["function"]["name"]] = ums_client

    FETCH_MCP_URL = "https://remote.mcpservers.org/fetch/mcp"
    fetch_host = urlparse(FETCH_MCP_URL).hostname

    try:
        # Resolve the host before attempting the MCP handshake. If the host is
        # unreachable, mcp's streamablehttp_client fails deep inside an anyio
        # task group and corrupts its cancel scope while tearing down, which can
        # spuriously cancel unrelated work later in this same task (e.g. the
        # OpenAI call). A plain DNS check fails cleanly and never enters that
        # code path.
        await asyncio.to_thread(socket.getaddrinfo, fetch_host, None)

        fetch_client = await MCPClient.create(FETCH_MCP_URL)
        fetch_tools = await fetch_client.get_tools()
        tools.extend(fetch_tools)
        for tool in fetch_tools:
            tool_name_client_map[tool["function"]["name"]] = fetch_client
    except BaseException as e:
        # anyio/mcp propagate connection failures (e.g. DNS errors) as CancelledError /
        # BaseExceptionGroup through the underlying task groups, which don't subclass
        # Exception — so a plain `except Exception` would not catch them here.
        print(f"⚠️  Could not connect to fetch MCP server, continuing without web search: {e}")

    agent = CustomAgentMCP(
        api_key=OPENAI_API_KEY,
        model="gpt-5.2",
        tools=tools,
        tool_name_client_map=tool_name_client_map,
    )

    messages = [
        Message(
            role=Role.SYSTEM,
            content=(
                "You are a helpful assistant that manages users in the User Management "
                "Service and can search the web to look up or verify information. Use "
                "the tools available to you to fulfill the user's request."
            ),
        )
    ]

    try:
        while True:
            user_input = input("\n> ").strip()

            if user_input.lower() == "exit":
                break

            messages.append(Message(role=Role.USER, content=user_input))

            ai_message = await agent.get_completion(messages)
            messages.append(ai_message)
    finally:
        await ums_client.close()



if __name__ == "__main__":
    asyncio.run(main())


# Check if Arkadiy Dobkin present as a user, if not then search info about him in the web and add him