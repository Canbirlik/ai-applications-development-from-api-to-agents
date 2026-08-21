from typing import Optional, Any

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, TextContent


class MCPClient:
    """Handles MCP server connection and tool execution"""

    def __init__(self, mcp_server_url: str) -> None:
        self.server_url = mcp_server_url
        self.session: Optional[ClientSession] = None
        self._streams_context = None
        self._session_context = None

    @classmethod
    async def create(cls, mcp_server_url: str) -> 'MCPClient':
        """Async factory method to create and connect MCPClient"""
        instance = cls(mcp_server_url)
        await instance.connect()
        return instance

    async def connect(self):
        """Connect to MCP server"""
        self._streams_context = streamablehttp_client(self.server_url)
        try:
            read_stream, write_stream, _ = await self._streams_context.__aenter__()

            self._session_context = ClientSession(read_stream, write_stream)
            self.session: ClientSession = await self._session_context.__aenter__()

            init_result = await self.session.initialize()
            print(init_result.model_dump_json(indent=2))
        except BaseException:
            # If anything fails partway through, close whatever was already
            # opened right here instead of leaving it for async-gen garbage
            # collection to close later from an unrelated task, which corrupts
            # anyio's cancel scopes and can cancel unrelated ongoing operations.
            await self.close()
            raise

    async def close(self):
        """Tear down the session/stream contexts, if they were opened"""
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
            self._session_context = None
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)
            self._streams_context = None

    async def get_tools(self) -> list[dict[str, Any]]:
        """Get available tools from MCP server"""
        if not self.session:
            raise RuntimeError("MCP client not connected. Call connect() first.")

        tools = await self.session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            }
            for tool in tools.tools
        ]

    async def call_tool(self, tool_name: str, tool_args: dict[str, Any]) -> Any:
        """Call a specific tool on the MCP server"""
        if not self.session:
            raise RuntimeError("MCP client not connected. Call connect() first.")

        print(f"    Calling `{tool_name}` with {tool_args}")

        tool_result: CallToolResult = await self.session.call_tool(tool_name, tool_args)
        content = tool_result.content

        print(f"    ⚙️: {content}\n")

        if isinstance(content, TextContent):
            return content.text

        return content

