import json
import logging
import uuid
from datetime import datetime, UTC
from typing import Optional, AsyncGenerator

import redis.asyncio as redis

from t13_final_task.task.agent.models import Message
from t13_final_task.task.agent.models import Role
from t13_final_task.task.agent.ums_agent import UMSAgent

logger = logging.getLogger(__name__)

_CONVERSATION_PREFIX = "conversation:"
_CONVERSATION_LIST_KEY = "conversations:list"

class ConversationManager:
    """Manages conversation lifecycle including AI interactions and persistence"""

    def __init__(self, ums_agent: UMSAgent, redis_client: redis.Redis, system_prompt: str):
        self.ums_agent = ums_agent
        self.redis = redis_client
        self._system_prompt = system_prompt
        logger.info("ConversationManager initialized")

    async def create_conversation(self, title: str) -> dict:
        """Create a new conversation"""
        #TODO:
        # - Build conversation dict: id (uuid4), title, messages=[], created_at, updated_at (UTC ISO)
        # - Persist to Redis: set by key, zadd to sorted list with timestamp score
        # - Return conversation dict
        now = datetime.now(UTC).isoformat()
        conversation = {
            "id": str(uuid.uuid4()),
            "title": title,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }

        await self._save_conversation(conversation)

        return conversation

    async def list_conversations(self) -> list[dict]:
        """List all conversations sorted by last update time"""
        #TODO:
        # - Get all conversation ids via zrevrange on _CONVERSATION_LIST_KEY
        # - For each id fetch from Redis, parse, append summary dict (id, title, created_at, updated_at, message_count)
        # - Return list of summaries
        conversation_ids = await self.redis.zrevrange(_CONVERSATION_LIST_KEY, 0, -1)

        summaries = []
        for raw_id in conversation_ids:
            conversation_id = raw_id.decode() if isinstance(raw_id, bytes) else raw_id
            conversation = await self.get_conversation(conversation_id)
            if conversation is None:
                continue

            summaries.append({
                "id": conversation["id"],
                "title": conversation["title"],
                "created_at": conversation["created_at"],
                "updated_at": conversation["updated_at"],
                "message_count": len(conversation["messages"]),
            })

        return summaries

    async def get_conversation(self, conversation_id: str) -> Optional[dict]:
        """Get a specific conversation"""
        #TODO:
        # - Get from Redis by key, return None if missing
        # - Return parsed conversation dict
        raw = await self.redis.get(_CONVERSATION_PREFIX + conversation_id)
        if raw is None:
            return None

        return json.loads(raw)

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation"""
        #TODO:
        # - Delete from Redis by key; return False if not found (deleted == 0)
        # - Remove from sorted list via zrem
        # - Return True
        deleted = await self.redis.delete(_CONVERSATION_PREFIX + conversation_id)
        if deleted == 0:
            return False

        await self.redis.zrem(_CONVERSATION_LIST_KEY, conversation_id)

        return True

    async def chat(
            self,
            user_message: Message,
            conversation_id: str,
            stream: bool = False
    ):
        """
        Process chat messages and return AI response.
        Automatically saves conversation state.
        """

        #TODO:
        # - Load conversation via get_conversation(); raise ValueError if not found
        # - Deserialize messages; if empty inject system prompt (Role.SYSTEM) first
        # - Append user_message
        # - If stream: return self._stream_chat(...), else return await self._non_stream_chat(...)
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            raise ValueError(f"Conversation '{conversation_id}' not found")

        messages = [
            Message(
                role=Role(msg["role"]),
                content=msg["content"],
                tool_call_id=msg.get("tool_call_id"),
                name=msg.get("name"),
                tool_calls=msg.get("tool_calls"),
            )
            for msg in conversation["messages"]
        ]

        if not messages:
            messages.append(Message(role=Role.SYSTEM, content=self._system_prompt))

        messages.append(user_message)

        if stream:
            return self._stream_chat(conversation_id, messages)

        return await self._non_stream_chat(conversation_id, messages)

    async def _stream_chat(
            self,
            conversation_id: str,
            messages: list[Message],
    ) -> AsyncGenerator[str, None]:
        """Handle streaming chat with automatic saving"""
        #TODO:
        # - Yield conversation_id as first SSE event
        # - Yield each chunk from ums_agent.stream_response(messages)
        # - Save messages via _save_conversation_messages()
        yield f"data: {json.dumps({'conversation_id': conversation_id})}\n\n"

        try:
            async for chunk in self.ums_agent.stream_response(messages):
                yield chunk
        except Exception as e:
            logger.exception("Error during streaming chat for conversation '%s'", conversation_id)
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        await self._save_conversation_messages(conversation_id, messages)

    async def _non_stream_chat(
            self,
            conversation_id: str,
            messages: list[Message],
    ) -> dict:
        """Handle non-streaming chat"""
        #TODO:
        # - Get ai_message via ums_agent.response(messages)
        # - Save messages via _save_conversation_messages()
        # - Return dict with content and conversation_id
        ai_message = await self.ums_agent.response(messages)
        messages.append(ai_message)

        await self._save_conversation_messages(conversation_id, messages)

        return {"content": ai_message.content, "conversation_id": conversation_id}

    async def _save_conversation_messages(
            self,
            conversation_id: str,
            messages: list[Message]
    ):
        """Save or update conversation messages"""
        #TODO:
        # - Fetch existing conversation from Redis, update messages (to_dict) and updated_at
        # - Persist via _save_conversation()
        conversation = await self.get_conversation(conversation_id)
        if conversation is None:
            logger.warning("Conversation '%s' not found while saving messages", conversation_id)
            return

        conversation["messages"] = [msg.to_dict() for msg in messages]
        conversation["updated_at"] = datetime.now(UTC).isoformat()

        await self._save_conversation(conversation)

    async def _save_conversation(self, conversation: dict):
        """Internal method to persist conversation to Redis"""
        #TODO:
        # - redis.set conversation by key (json.dumps)
        # - redis.zadd to sorted list with current timestamp score
        await self.redis.set(_CONVERSATION_PREFIX + conversation["id"], json.dumps(conversation))
        await self.redis.zadd(_CONVERSATION_LIST_KEY, {conversation["id"]: datetime.now(UTC).timestamp()})
