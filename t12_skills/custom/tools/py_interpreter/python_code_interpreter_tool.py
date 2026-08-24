from pathlib import Path
from typing import Any, Optional

from t12_skills.custom.file_utils import get_file_content
from t12_skills.custom.mcp.mcp_client import T12MCPClient
from t12_skills.custom.mcp.mcp_tool_model import MCPToolModel
from t12_skills.custom.tools.base import BaseTool
from t12_skills.custom.tools.py_interpreter._response import _ExecutionResult


class PythonCodeInterpreterTool(BaseTool):

    def __init__(
            self,
            mcp_client: T12MCPClient,
            mcp_tool_models: list[MCPToolModel],
            tool_name: str,
            skills_dir: Path
    ):
        self._mcp_client = mcp_client
        self._skills_dir = skills_dir

        self._code_execute_tool: Optional[MCPToolModel] = None
        #TODO:
        # - Iterate over mcp_tool_models and assign the one matching tool_name to self._code_execute_tool
        # - If not found, raise ValueError listing the available tool names
        for tool in mcp_tool_models:
            if tool.name == tool_name:
                self._code_execute_tool = tool
                break

        if self._code_execute_tool is None:
            available = ", ".join(tool.name for tool in mcp_tool_models)
            raise ValueError(f"Tool '{tool_name}' not found. Available tools: {available}")

    @classmethod
    async def create(
            cls,
            mcp_url: str,
            tool_name: str,
            skills_dir: Path
    ) -> 'PythonCodeInterpreterTool':
        """Async factory method to create PythonCodeInterpreterTool."""
        #TODO:
        # - Create a T12MCPClient by connecting to mcp_url (use T12MCPClient.create)
        # - Fetch the available tools from the MCP client
        # - Instantiate and return cls with the client, tools, tool_name, and skills_dir
        mcp_client = await T12MCPClient.create(mcp_url)
        mcp_tool_models = await mcp_client.get_tools()
        return cls(mcp_client, mcp_tool_models, tool_name, skills_dir)

    @property
    def name(self) -> str:
        #TODO: Return the tool name from self._code_execute_tool
        assert self._code_execute_tool is not None
        return self._code_execute_tool.name

    @property
    def description(self) -> str:
        #TODO: Return the tool description from self._code_execute_tool
        assert self._code_execute_tool is not None
        return self._code_execute_tool.description

    @property
    def parameters(self) -> dict[str, Any]:
        #TODO:
        # - Start from self._code_execute_tool.parameters (spread it into a new dict)
        # - Add an extra optional string property "script_path" describing that the tool
        #   will prepend the file content to the code before execution
        # - Return the extended parameters dict
        assert self._code_execute_tool is not None
        parameters = {**self._code_execute_tool.parameters}
        properties = {**parameters.get("properties", {})}
        properties["script_path"] = {
            "type": "string",
            "description": (
                "Optional path to a skill file (relative to the skills directory, e.g. "
                "'/unit-converter/scripts/convert.py'). Its content is prepended to `code` "
                "before execution."
            ),
        }
        parameters["properties"] = properties
        return parameters

    async def _execute(self, arguments: dict[str, Any]) -> str:
        #TODO:
        # - If arguments contains a non-empty "script_path":
        #   - Resolve the full path by combining self._skills_dir with the stripped script_path
        #   - Read the script content using `get_file_content` method
        #   - Build args with "code" = script_content + "\n\n" + arguments["code"]
        #     and "session_id" = arguments.get("session_id", "")
        # - Otherwise use arguments directly as args
        # - Call self._mcp_client.call_tool with the tool name and args
        # - Parse the returned content into _ExecutionResult using model_validate_json
        # - Return the result serialized as JSON using model_dump_json
        script_path = arguments.get("script_path")

        if script_path:
            full_path = self._skills_dir / script_path.lstrip("/")
            script_content = get_file_content(full_path)
            args = {
                "code": script_content + "\n\n" + arguments["code"],
                "session_id": arguments.get("session_id", ""),
            }
        else:
            args = arguments

        result = await self._mcp_client.call_tool(self.name, args)
        execution_result = _ExecutionResult.model_validate_json(result)
        return execution_result.model_dump_json()

    async def close(self) -> None:
        """Close the underlying MCP connection."""
        await self._mcp_client.close()
