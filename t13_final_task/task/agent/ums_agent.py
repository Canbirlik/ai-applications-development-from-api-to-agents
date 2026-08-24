import json
import logging
from collections import defaultdict
from typing import AsyncGenerator

from openai import AsyncOpenAI

from t13_final_task.task.agent.models import Message
from t13_final_task.task.agent.models import Role
from t13_final_task.task.agent.guardrail import UMSDataGuardrail
from t13_final_task.task.agent.tools.base import BaseTool

logger = logging.getLogger(__name__)


class UMSAgent:
    """Handles AI model interactions and integrates with MCP client"""

    def __init__(
            self,
            api_key: str,
            model: str,
            tools: list[BaseTool]
    ):
        #TODO:
        # - Store tools as dict `tool.name: tool`
        # - Store tools schemas list
        # - Store model
        # - Init AsyncOpenAI
        # - Init UMSDataGuardrail
        self.tools = {tool.name: tool for tool in tools}
        self.tools_schemas = [tool.schema for tool in tools]
        self.model = model
        self.async_openai = AsyncOpenAI(api_key=api_key)
        self.guardrail = UMSDataGuardrail()

    async def response(self, messages: list[Message]) -> Message:
        """Non-streaming completion with tool calling support"""
        #TODO:
        # 1. Build request_data: model, messages (each .to_dict()), tools schemas, stream=False
        # 2. Call async_openai chat completions with request_data
        # 3. Build ai_message (Role.ASSISTANT) from response content
        # 4. If response has tool_calls, assign them to ai_message.tool_calls
        # 5. If ai_message has tool_calls: append ai_message to messages, call _call_tools(),
        #    then make recursive call
        # 6. Return ai_message
        request_data = {
            "model": self.model,
            "messages": [msg.to_dict() for msg in messages],
            "tools": self.tools_schemas,
            "stream": False,
        }

        completion = await self.async_openai.chat.completions.create(**request_data)
        choice = completion.choices[0]

        ai_message = Message(role=Role.ASSISTANT, content=choice.message.content or "")

        if choice.message.tool_calls:
            ai_message.tool_calls = [
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

        if ai_message.tool_calls:
            messages.append(ai_message)
            await self._call_tools(ai_message, messages)
            return await self.response(messages)

        return ai_message

    async def stream_response(self, messages: list[Message]) -> AsyncGenerator[str, None]:
        """
        Streaming completion with tool calling support.
        Yields SSE-formatted chunks.
        """
        #TODO:
        # 1. Build request_data: model, messages (each .to_dict()), tools schemas, stream=True
        # 2. Stream via async_openai chat completions; buffer content and tool_deltas per chunk
        # 3. If tool_deltas after stream:
        #    - Collect tool_calls via _collect_tool_calls(), build ai_message, append to messages
        #    - Notify frontend about each tool call (type: "call") and result (type: "result") via SSE
        #    - Recursively yield from self.stream_response(messages), then return
        # 4. If no tool calls: append final assistant message
        # 5. Yield final SSE chunk with finish_reason="stop", then yield "data: [DONE]\n\n"
        request_data = {
            "model": self.model,
            "messages": [msg.to_dict() for msg in messages],
            "tools": self.tools_schemas,
            "stream": True,
        }

        stream = await self.async_openai.chat.completions.create(**request_data)

        content = ""
        tool_deltas = []

        async for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                content += delta.content

            if delta.tool_calls:
                tool_deltas.extend(delta.tool_calls)

            # Relay the raw OpenAI chunk so the frontend can read choices[0].delta.content directly
            yield f"data: {chunk.model_dump_json()}\n\n"

        if tool_deltas:
            tool_calls = self._collect_tool_calls(tool_deltas)
            ai_message = Message(role=Role.ASSISTANT, content=content, tool_calls=tool_calls)
            messages.append(ai_message)

            for tool_call in tool_calls:
                call_event = {
                    "tool_activity": {
                        "type": "call",
                        "name": tool_call["function"]["name"],
                        "arguments": tool_call["function"]["arguments"],
                    },
                }
                yield f"data: {json.dumps(call_event)}\n\n"

            before = len(messages)
            await self._call_tools(ai_message, messages, silent=True)
            tool_messages = messages[before:]

            for tool_call, tool_message in zip(tool_calls, tool_messages):
                result_event = {
                    "tool_activity": {
                        "type": "result",
                        "name": tool_call["function"]["name"],
                        "content": tool_message.content,
                    },
                }
                yield f"data: {json.dumps(result_event)}\n\n"

            async for chunk_str in self.stream_response(messages):
                yield chunk_str
            return

        messages.append(Message(role=Role.ASSISTANT, content=content))

        yield "data: [DONE]\n\n"

    def _collect_tool_calls(self, tool_deltas):
        """Convert streaming tool call deltas to complete tool calls"""
        #TODO:
        # 1. Use defaultdict keyed by delta.index; each entry has shape:
        #    {"id": None, "function": {"arguments": "", "name": None}, "type": None}
        # 2. For each delta: accumulate id, function.name, function.arguments (concatenate), type
        # 3. Return list(tool_dict.values())
        tool_dict = defaultdict(lambda: {"id": None, "function": {"arguments": "", "name": None}, "type": None})

        for delta in tool_deltas:
            idx = delta.index
            if delta.id: tool_dict[idx]["id"] = delta.id
            if delta.function.name: tool_dict[idx]["function"]["name"] = delta.function.name
            if delta.function.arguments: tool_dict[idx]["function"]["arguments"] += delta.function.arguments
            if delta.type: tool_dict[idx]["type"] = delta.type

        return list(tool_dict.values())

    async def _call_tools(self, ai_message: Message, messages: list[Message], silent: bool = False):
        """Execute tool calls using MCP client"""
        #TODO:
        # Iterate through tool_calls:
        #   - Extract tool_name and arguments
        #   - If tool found in self.tools:
        #       - Execute tool call
        #       - Append tool message to messages
        #   - If tool not found: append a Tool Message error content and dont forget about tool_call_id
        assert ai_message.tool_calls is not None
        for tool_call in ai_message.tool_calls:
            tool_call_id = tool_call["id"]
            tool_name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"])

            tool = self.tools.get(tool_name)

            if tool is None:
                tool_message = Message(
                    role=Role.TOOL,
                    tool_call_id=tool_call_id,
                    content=f"Error: tool '{tool_name}' not found",
                )
            else:
                if not silent:
                    logger.info("Calling tool '%s' with %s", tool_name, arguments)
                tool_message = await tool.execute(tool_call_id, arguments)

            #TODO 2:
            # Implement it ONLY after you started the app
            # Make PII filtering for tool call result
            tool_message.content = self.guardrail.redact(tool_message.content)

            messages.append(tool_message)