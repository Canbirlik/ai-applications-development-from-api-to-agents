from typing import Any

from t10_mcp_advanced.mcp_server.tools.users.base import BaseUserServiceTool


class SearchUsersTool(BaseUserServiceTool):

    @property
    def name(self) -> str:
        #TODO: Provide tool name as `search_users`
        return "search_users"

    @property
    def description(self) -> str:
        #TODO: Provide description of this tool
        return "Search for users in the User Service by name, surname, email and/or gender."

    @property
    def input_schema(self) -> dict[str, Any]:
        #TODO:
        # Provide tool params Schema:
        # - name: str
        # - surname: str
        # - email: str
        # - gender: str
        # None of them are required (see UserClient.search_users method)
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "First name to search for (partial, case-insensitive)."},
                "surname": {"type": "string", "description": "Last name to search for (partial, case-insensitive)."},
                "email": {"type": "string", "description": "Email to search for (partial, case-insensitive)."},
                "gender": {"type": "string", "description": "Exact gender match (male, female, other, prefer_not_to_say)."}
            },
            "required": []
        }

    async def execute(self, arguments: dict[str, Any]) -> str:
        #TODO:
        # Call user_client search_users (with `**arguments`) and return its results (it is async, don't forget to await)
        return self._user_client.search_users(**arguments)