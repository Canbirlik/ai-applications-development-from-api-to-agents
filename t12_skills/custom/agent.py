import json

from openai import OpenAI

from commons.models.message import Message
from commons.models.role import Role
from t12_skills.custom.tools.base import BaseTool


class T12Agent:

    def __init__(self, client: OpenAI, model: str, tools: list[BaseTool] | None = None):
        self._client = client
        self._model = model
        self._tools: dict[str, BaseTool] = {tool.name: tool for tool in tools}
        self._tools_schemas = [tool.schema for tool in tools] if tools else []
        print(json.dumps(self._tools_schemas, indent=4))

    async def chat_completion(self, messages: list[Message], log_messages: bool = False) -> Message:
        if log_messages:
            print("\n--- REQUEST ---")
            print(json.dumps([msg.to_dict() for msg in messages], indent=2, default=str))

        return await self._chat_completion(messages, log_messages)

    async def _chat_completion(self, messages: list[Message], log_messages: bool = False) -> Message:
        #TODO:
        # - Build a request dict with model, messages (convert each to dict), and tools schemas
        # - Call self._client.chat.completions.create and get the first choice
        # - Create an assistant Message with empty content
        # - If choice.message.content is set, assign it to the assistant message
        # - If choice.message.tool_calls is set, serialize them into assistant_msg.tool_calls
        #   as a list of dicts with keys: id, type, function (name + arguments)
        # - If finish_reason is "tool_calls":
        #   - Append assistant_msg to messages
        #   - Dispatch tool calls and extend messages with the resulting tool messages
        #   - Optionally log if log_messages
        #   - Recursively call _chat_completion and return the result
        # - Optionally log if log_messages, then print the assistant reply with "🤖: " prefix
        # - Return the assistant message
        request = {
            "model": self._model,
            "messages": [msg.to_dict() for msg in messages],
            "tools": self._tools_schemas,
        }

        response = self._client.chat.completions.create(**request)
        choice = response.choices[0]

        assistant_msg = Message(role=Role.ASSISTANT, content="")

        if choice.message.content:
            assistant_msg.content = choice.message.content

        if choice.message.tool_calls:
            assistant_msg.tool_calls = [
                {
                    "id": tool_call.id,
                    "type": tool_call.type,
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                for tool_call in choice.message.tool_calls
            ]

        if choice.finish_reason == "tool_calls":
            messages.append(assistant_msg)
            tool_messages = await self._dispatch_tool_calls(choice.message.tool_calls)
            messages.extend(tool_messages)

            if log_messages:
                print("\n--- TOOL RESULTS ---")
                print(json.dumps([msg.to_dict() for msg in tool_messages], indent=2, default=str))

            return await self._chat_completion(messages, log_messages)

        if log_messages:
            print("\n--- RESPONSE ---")
            print(json.dumps(assistant_msg.to_dict(), indent=2, default=str))

        print(f"🤖: {assistant_msg.content}")

        return assistant_msg

    async def _dispatch_tool_calls(self, tool_calls) -> list[Message]:
        #TODO:
        # - Iterate over each tool call
        # - Look up the tool by function name in self._tools
        # - If the tool is not found, set content to an error string
        # - Otherwise call tool.execute with the tool call ID and parsed JSON arguments,
        #   then take the content from the resulting message
        # - Append a TOOL role Message (with tool_call_id, name, content) for each call
        # - Return the list of tool messages
        tool_messages = []

        for tool_call in tool_calls:
            function_name = tool_call.function.name
            tool = self._tools.get(function_name)

            if tool is None:
                content = f"Unknown function: {function_name}"
            else:
                arguments = json.loads(tool_call.function.arguments)
                result_message = await tool.execute(tool_call.id, arguments)
                content = result_message.content

            tool_messages.append(
                Message(
                    role=Role.TOOL,
                    tool_call_id=tool_call.id,
                    name=function_name,
                    content=content,
                )
            )

        return tool_messages
