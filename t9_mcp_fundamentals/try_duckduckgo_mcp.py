import asyncio

from commons.constants import OPENAI_API_KEY
from commons.models.message import Message
from commons.models.role import Role
from t9_mcp_fundamentals.agent.agent import AgentMCPFundamentals
from t9_mcp_fundamentals.agent.mcp_clients.stdio import StdioMCPClient

GENERIC_SYSTEM_PROMPT = "You are a helpful assistant. Use the tools available to you to answer questions."


async def main():
    async with StdioMCPClient(docker_image="mcp/duckduckgo:latest") as mcp_client:
        tools = await mcp_client.get_tools()
        print("\n🔧 Available Tools:")
        for tool in tools:
            print(f"  - {tool['function']['name']}: {tool['function']['description']}")

        agent = AgentMCPFundamentals(
            api_key=OPENAI_API_KEY,
            model="gpt-5.2",
            tools=tools,
            mcp_client=mcp_client,
        )

        messages = [
            Message(role=Role.SYSTEM, content=GENERIC_SYSTEM_PROMPT),
            Message(role=Role.USER, content="What is the weather in Kyiv now?"),
        ]

        ai_message = await agent.get_response(messages)
        print("\nFinal answer:", ai_message.content)


if __name__ == "__main__":
    asyncio.run(main())
