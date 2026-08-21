from typing import Any

import requests

from commons.constants import OPENAI_RESPONSES_ENDPOINT
from t8_agent.task.tools.base import BaseTool


class WebSearchTool(BaseTool):

    def __init__(self, open_ai_api_key: str):
        self.__api_key = f"Bearer {open_ai_api_key}"
        self.__endpoint = OPENAI_RESPONSES_ENDPOINT

    @property
    def name(self) -> str:
        #TODO: Provide tool name as `web_search_tool`
        return "web_search_tool"

    @property
    def description(self) -> str:
        #TODO: Provide description of this tool
        return "Search the web for up-to-date information on a given topic."

    @property
    def input_schema(self) -> dict[str, Any]:
        #TODO: Provide tool params Schema (it applies `request` string to search by)
        return {
            "type": "object",
            "properties": {
                "request": {"type": "string", "description": "The search query to look up on the web."}
            },
            "required": ["request"],
        }

    def execute(self, arguments: dict[str, Any]) -> str:
        #TODO:
        # https://developers.openai.com/api/docs/guides/tools-web-search
        # 1. Make POST call to `gpt-5.2` with request "tools": [{"type": "web_search"}],
        # 4. Check if response status is 200 and if yes then return message content, otherwise return `f"Error: {response.status_code} {response.text}"`
        headers = {
            "Authorization": self.__api_key,
            "Content-Type": "application/json",
        }
        request_data = {
            "model": "gpt-5.2",
            "input": arguments["request"],
            "tools": [{"type": "web_search"}],
        }

        response = requests.post(url=self.__endpoint, headers=headers, json=request_data)

        if response.status_code == 200:
            data = response.json()
            return self.__extract_output_text(data.get("output", []))

        return f"Error: {response.status_code} {response.text}"

    @staticmethod
    def __extract_output_text(output: list[dict]) -> str:
        texts = []
        for item in output:
            if item.get("type") == "message":
                for content_part in item.get("content", []):
                    if content_part.get("type") == "output_text":
                        texts.append(content_part.get("text", ""))
        return "".join(texts)