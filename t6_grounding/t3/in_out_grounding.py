import asyncio
import json
from typing import Any, cast

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field, SecretStr

from commons.constants import OPENAI_API_KEY
from t6_grounding.user_service_client import UserServiceClient

#TODO: Info about app:
# HOBBIES SEARCHING WIZARD
# Searches users by hobbies and provides their full info in JSON format:
#   Input: `I need people who love to go to mountains`
#   Output:
#     ```json
#       "rock climbing": [{full user info JSON},...],
#       "hiking": [{full user info JSON},...],
#       "camping": [{full user info JSON},...]
#     ```
# ---
# 1. Since we are searching hobbies that persist in `about_me` section - we need to embed only user `id` and `about_me`!
#    It will allow us to reduce context window significantly.
# 2. Pay attention that every 5 minutes in User Service will be added new users and some will be deleted. We will at the
#    'cold start' add all users for current moment to vectorstor and with each user request we will update vectorstor on
#    the retrieval step, we will remove deleted users and add new - it will also resolve the issue with consistency
#    within this 2 services and will reduce costs (we don't need on each user request load vectorstor from scratch and pay for it).
# 3. We ask LLM make NEE (Named Entity Extraction) https://cloud.google.com/discover/what-is-entity-extraction?hl=en
#    and provide response in format:
#    {
#       "{hobby}": [{user_id}, 2, 4, 100...]
#    }
#    It allows us to save significant money on generation, reduce time on generation and eliminate possible
#    hallucinations (corrupted personal info or removed some parts of PII (Personal Identifiable Information)). After
#    generation we also need to make output grounding (fetch full info about user and in the same time check that all
#    presented IDs are correct).
# 4. In response we expect JSON with grouped users by their hobbies.
# ---
# This sample is based on the real solution where one Service provides our Wizard with user request, we fetch all
# required data and then returned back to 1st Service response in JSON format.
# ---
# Useful links:
# Chroma DB: https://docs.langchain.com/oss/python/integrations/vectorstores/index#chroma
# Document#id: https://docs.langchain.com/oss/python/langchain/knowledge-base#1-documents-and-document-loaders
# ---
# TASK:
# Implement such application as described on the `flow.png` with adaptive vector based grounding and 'lite' version of
# output grounding (verification that such user exist and fetch full user info)

SYSTEM_PROMPT = """You are a Named Entity Extraction (NEE) system for a hobbies search wizard.

You will be given a RAG CONTEXT of user profiles (each with an `id` and their `about_me` text) that were
already pre-filtered by a semantic similarity search against the user's request, plus the user's original
request as USER REQUEST.

Your task:
- Identify which hobbies from the USER REQUEST are relevant.
- For each relevant hobby, collect the `id`s (from the RAG CONTEXT ONLY) of the users whose `about_me`
  text indicates they actually have that hobby.
- Only use ids that are present in the RAG CONTEXT - never invent or guess an id.
- If no user in the RAG CONTEXT matches any hobby from the request, return an empty list of groups.
"""

USER_PROMPT = """##RAG CONTEXT (user id and about_me):
{context}


##USER REQUEST:
{query}"""


class HobbyGroup(BaseModel):
    hobby: str = Field(description="Hobby name extracted from the user request")
    user_ids: list[int] = Field(description="IDs (from RAG CONTEXT only) of users matching this hobby")


class HobbyGroups(BaseModel):
    groups: list[HobbyGroup] = Field(
        description="Users grouped by hobby",
        default_factory=list
    )


class HobbySearchWizard:
    def __init__(self, embeddings: OpenAIEmbeddings):
        self.embeddings = embeddings
        self._llm_client = OpenAI(api_key=OPENAI_API_KEY)
        self._user_client = UserServiceClient()
        self.vectorstore = Chroma(embedding_function=embeddings, collection_name="user_hobbies")

    async def __aenter__(self):
        print("🔎 Loading all users...")
        users = self._user_client.get_all_users()

        print(f"↗️ Embedding {len(users)} user profiles (id + about_me only)...")
        await self._add_users_with_batching(users, batch_size=100)

        print("✅ Vectorstore is ready.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    @staticmethod
    def _to_document(user: dict[str, Any]) -> Document:
        return Document(page_content=user.get("about_me") or "", metadata={"id": user["id"]})

    async def _add_users_with_batching(self, users: list[dict[str, Any]], batch_size: int = 100) -> None:
        if not users:
            return

        batches = [users[i:i + batch_size] for i in range(0, len(users), batch_size)]
        coroutines = [
            self.vectorstore.aadd_documents(
                [self._to_document(user) for user in batch],
                ids=[str(user["id"]) for user in batch],
            )
            for batch in batches
        ]
        await asyncio.gather(*coroutines)

    async def _sync_vectorstore(self) -> None:
        users = self._user_client.get_all_users()
        current_ids = {str(user["id"]) for user in users}

        existing_ids = set(self.vectorstore.get(include=[])["ids"])

        deleted_ids = existing_ids - current_ids
        if deleted_ids:
            print(f"🗑️ Removing {len(deleted_ids)} deleted users from vectorstore...")
            await self.vectorstore.adelete(ids=list(deleted_ids))

        new_users = [user for user in users if str(user["id"]) not in existing_ids]
        if new_users:
            print(f"➕ Adding {len(new_users)} new users to vectorstore...")
            await self._add_users_with_batching(new_users, batch_size=100)

    async def retrieve_context(self, query: str, k: int = 30, score: float = 0.1) -> str:
        print("Retrieving context...")
        await self._sync_vectorstore()

        results = await self.vectorstore.asimilarity_search_with_relevance_scores(query, k=k, score_threshold=score)

        context_parts = []
        for doc, relevance_score in results:
            user_id = doc.metadata.get("id")
            context_parts.append(f"id: {user_id}\n  about_me: {doc.page_content}")
            print(f"Retrieved (Score: {relevance_score:.3f}): id={user_id}")

        print("=" * 100 + "\n")
        return "\n\n".join(context_parts)

    def augment_prompt(self, query: str, context: str) -> str:
        return USER_PROMPT.format(context=context, query=query)

    def generate_answer(self, augmented_prompt: str) -> HobbyGroups:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": augmented_prompt},
        ]

        completion = self._llm_client.beta.chat.completions.parse(
            model="gpt-4o",
            temperature=0.0,
            messages=cast(list[ChatCompletionMessageParam], messages),
            response_format=HobbyGroups,
        )

        return completion.choices[0].message.parsed or HobbyGroups()

    async def output_grounding(self, hobby_groups: HobbyGroups) -> dict[str, list[dict[str, Any]]]:
        results: dict[str, list[dict[str, Any]]] = {}
        for group in hobby_groups.groups:
            users = []
            for user_id in group.user_ids:
                try:
                    users.append(await self._user_client.get_user(user_id))
                except Exception:
                    print(f"⚠️ User {user_id} no longer exists, skipping.")
            if users:
                results[group.hobby] = users

        return results


async def main():
    embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small",
        api_key=SecretStr(OPENAI_API_KEY),
        dimensions=384,
    )

    async with HobbySearchWizard(embeddings) as wizard:
        print("Query samples:")
        print(" - I need people who love to go to mountains")
        while True:
            user_question = input("> ").strip()
            if user_question.lower() in ["quit", "exit"]:
                break
            if not user_question:
                continue

            context = await wizard.retrieve_context(user_question)
            augmented_prompt = wizard.augment_prompt(user_question, context)
            hobby_groups = wizard.generate_answer(augmented_prompt)
            grounded_results = await wizard.output_grounding(hobby_groups)

            print("\n=== SEARCH RESULTS ===")
            print(json.dumps(grounded_results, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())