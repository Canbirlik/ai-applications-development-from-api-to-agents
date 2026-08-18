import json
import aiohttp
import requests

from commons.models.message import Message
from commons.models.role import Role
from t1_llm_api.base_client import AIClient


class CustomGeminiAIClient(AIClient):
    """
    Custom HTTP client for Google Gemini API.

    This implementation uses raw HTTP requests (requests/aiohttp) instead of
    the official SDK, demonstrating how to interact with Gemini's API directly
    and handle its Server-Sent Events (SSE) streaming format.
    """

    def response(self, messages: list[Message], **kwargs) -> Message:
        """
        Get a synchronous response using raw HTTP POST request.

        Args:
            messages (list[Message]): The conversation history.
            **kwargs: Additional parameters like max_tokens (default: 1024).

        Returns:
            Message: The AI's response message.

        Raises:
            ValueError: If the API response contains no candidates.
            Exception: If the HTTP request fails (non-200 status code).

        Note:
            The URL is constructed by appending ':generateContent' to the model endpoint.
            Uses 'x-goog-api-key' header for authentication.
            Response candidates contain content parts that are concatenated.
        """
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        max_tokens = kwargs.pop("max_tokens", 1024)
        request_data = {
            "system_instruction": {"parts": [{"text": self._system_prompt}]},
            "contents": [self._to_content(message) for message in messages],
            "generationConfig": {"maxOutputTokens": max_tokens, **kwargs},
        }
        url = f"{self._endpoint}/{self._model_name}:generateContent"

        response = requests.post(url=url, headers=headers, json=request_data)

        if response.status_code == 200:
            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("No candidates have been present in the response")
            parts = candidates[0].get("content", {}).get("parts", [])
            content = "".join(part.get("text", "") for part in parts)
            print(content)
            return Message(Role.ASSISTANT, content)
        else:
            raise Exception(f"HTTP {response.status_code}: {response.text}")

    async def stream_response(self, messages: list[Message], **kwargs) -> Message:
        """
        Get a streaming response using raw HTTP with Server-Sent Events (SSE).

        The response is streamed using Gemini's SSE format, with text chunks
        printed immediately as they arrive.

        Args:
            messages (list[Message]): The conversation history.
            **kwargs: Additional parameters like max_tokens (default: 1024).

        Returns:
            Message: The complete AI response message after all chunks are received.

        Note:
            The URL is constructed with ':streamGenerateContent?alt=sse' endpoint.
            Uses Server-Sent Events (SSE) format where each line starts with "data: ".
            Each SSE chunk contains candidates with content parts.
            Each text chunk is printed to stdout as it arrives.
        """
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        max_tokens = kwargs.pop("max_tokens", 1024)
        request_data = {
            "system_instruction": {"parts": [{"text": self._system_prompt}]},
            "contents": [self._to_content(message) for message in messages],
            "generationConfig": {"maxOutputTokens": max_tokens, **kwargs},
        }
        url = f"{self._endpoint}/{self._model_name}:streamGenerateContent?alt=sse"

        content = ""
        async with aiohttp.ClientSession() as session:
            async with session.post(url=url, headers=headers, json=request_data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"HTTP {response.status}: {error_text}")

                async for line in response.content:
                    decoded_line = line.decode("utf-8").strip()
                    if not decoded_line.startswith("data: "):
                        continue

                    chunk = json.loads(decoded_line[len("data: "):])
                    candidates = chunk.get("candidates", [])
                    if not candidates:
                        continue

                    parts = candidates[0].get("content", {}).get("parts", [])
                    text = "".join(part.get("text", "") for part in parts)
                    if text:
                        print(text, end="", flush=True)
                        content += text
        print()

        return Message(Role.ASSISTANT, content)

    @staticmethod
    def _to_content(message: Message) -> dict:
        role = "model" if message.role == Role.ASSISTANT else "user"
        return {"role": role, "parts": [{"text": message.content}]}