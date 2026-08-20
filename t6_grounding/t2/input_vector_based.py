import asyncio
from typing import Any, cast

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStore
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import SecretStr

from commons.constants import OPENAI_API_KEY
from t6_grounding.user_service_client import UserServiceClient

#TODO:
# Define SYSTEM_PROMPT - instructs the LLM to act as a RAG-powered assistant:
#   - The user message contains two sections: RAG CONTEXT and USER QUESTION
#   - Answer ONLY based on the provided RAG CONTEXT and conversation history
#   - If no relevant information exists in RAG CONTEXT, state that the question cannot be answered
SYSTEM_PROMPT = """You are a RAG-powered assistant. The user message is structured in two sections:
- RAG CONTEXT: user data retrieved via similarity search for the current question
- USER QUESTION: the actual question asked by the user

Rules:
- Answer ONLY based on the information provided in the RAG CONTEXT and the conversation history.
- If the RAG CONTEXT does not contain relevant information, state clearly that the question cannot be
  answered based on the available data.
"""

#TODO:
# Define USER_PROMPT template with two placeholders:
#   - {context} - the retrieved user data
#   - {query}   - the user's question
USER_PROMPT = """##RAG CONTEXT:
{context}


##USER QUESTION:
{query}"""


def format_user_document(user: dict[str, Any]) -> str:
    #TODO:
    # - Build a string starting with "User:\n"
    # - For each key-value pair in the user dict, add an indented "  key: value\n" line
    # - Add a blank line at the end
    # - Return the formatted string
    document = "User:\n"
    for key, value in user.items():
        document += f"  {key}: {value}\n"
    document += "\n"

    return document


class UserRAG:
    def __init__(self, embeddings: OpenAIEmbeddings):
        self.embeddings = embeddings
        self._llm_client = OpenAI(api_key=OPENAI_API_KEY)
        self.vectorstore: VectorStore | None = None

    async def __aenter__(self):
        #TODO:
        # - Print "🔎 Loading all users..."
        # - Fetch all users via UserServiceClient().get_all_users()
        # - Print f"Formatting {len(users)} user documents..."
        # - Create a list of Document objects, each with page_content=format_user_document(user)
        # - Print f"↗️ Creating embeddings and vectorstore for {len(documents)} documents..."
        # - Call await self._create_vectorstore_with_batching(documents, batch_size=100)
        #   and assign the result to self.vectorstore
        # - Print "✅ Vectorstore is ready."
        # - Return self
        print("🔎 Loading all users...")
        users = UserServiceClient().get_all_users()

        print(f"Formatting {len(users)} user documents...")
        documents = [Document(page_content=format_user_document(user)) for user in users]

        print(f"↗️ Creating embeddings and vectorstore for {len(documents)} documents...")
        self.vectorstore = await self._create_vectorstore_with_batching(documents, batch_size=100)

        print("✅ Vectorstore is ready.")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def _create_vectorstore_with_batching(self, documents: list[Document], batch_size: int = 100):
        #TODO:
        # - Split documents into batches of batch_size using list slicing
        # - Create a list of FAISS.afrom_documents(batch, self.embeddings) coroutines for each batch
        # - Run all coroutines IN PARALLEL using asyncio.gather(..., return_exceptions=True)
        # - Iterate over batch results:
        #   - If final_vectorstore is None, set it to the current batch result
        #   - Otherwise, call final_vectorstore.merge_from(batch_vectorstore) to combine them
        # - If final_vectorstore is still None after all batches, raise Exception("All batches failed to process")
        # - Return the final merged vectorstore
        batches = [documents[i:i + batch_size] for i in range(0, len(documents), batch_size)]

        coroutines = [FAISS.afrom_documents(batch, self.embeddings) for batch in batches]
        batch_results = await asyncio.gather(*coroutines, return_exceptions=True)

        final_vectorstore = None
        for batch_vectorstore in batch_results:
            if isinstance(batch_vectorstore, BaseException):
                continue
            if final_vectorstore is None:
                final_vectorstore = batch_vectorstore
            else:
                final_vectorstore.merge_from(batch_vectorstore)

        if final_vectorstore is None:
            raise Exception("All batches failed to process")

        return final_vectorstore

    async def retrieve_context(self, query: str, k: int = 10, score: float = 0.1) -> str:
        print("Retrieving context...")
        #TODO:
        # - Call self.vectorstore.similarity_search_with_relevance_scores(query, k=k, score_threshold=score)
        # - Iterate over (doc, relevance_score) pairs:
        #   - Append doc.page_content to context_parts
        #   - Print f"Retrieved (Score: {relevance_score:.3f}): {doc.page_content}"
        # - Print a separator line of 100 "=" characters followed by "\n"
        # - Return all context_parts joined with "\n\n"
        assert self.vectorstore is not None, "Vectorstore is not initialized, use 'async with UserRAG(...)'"
        results = self.vectorstore.similarity_search_with_relevance_scores(query, k=k, score_threshold=score)

        context_parts = []
        for doc, relevance_score in results:
            context_parts.append(doc.page_content)
            print(f"Retrieved (Score: {relevance_score:.3f}): {doc.page_content}")

        print("=" * 100 + "\n")
        return "\n\n".join(context_parts)

    def augment_prompt(self, query: str, context: str) -> str:
        #TODO:
        # - Return USER_PROMPT formatted with context and query
        return USER_PROMPT.format(context=context, query=query)

    def generate_answer(self, augmented_prompt: str) -> str:
        #TODO:
        # - Build a messages list with SYSTEM_PROMPT as system and augmented_prompt as user
        # - Call self._llm_client.chat.completions.create with model='gpt-4o-mini', temperature=0.0
        # - Return the response content string (default to "" if None)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": augmented_prompt},
        ]

        completion = self._llm_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.0,
            messages=cast(list[ChatCompletionMessageParam], messages),
        )

        return completion.choices[0].message.content or ""


async def main():
    embeddings = OpenAIEmbeddings(
        model='text-embedding-3-small',
        api_key=SecretStr(OPENAI_API_KEY),
        dimensions=384,
    )

    async with UserRAG(embeddings) as rag:
        print("Query samples:")
        print(" - I need user emails that filled with hiking and psychology")
        print(" - Who is John?")
        while True:
            user_question = input("> ").strip()
            if user_question.lower() in ['quit', 'exit']:
                break

            #TODO:
            # - Call await rag.retrieve_context(user_question) and store in context
            # - Call rag.augment_prompt(user_question, context) and store in augmented_prompt
            # - Call rag.generate_answer(augmented_prompt) and print the answer
            context = await rag.retrieve_context(user_question)
            augmented_prompt = rag.augment_prompt(user_question, context)
            answer = rag.generate_answer(augmented_prompt)
            print(f"\nAnswer: {answer}\n")


asyncio.run(main())

# The problems with Vector based Grounding approach are:
#   - In current solution we fetched all users once, prepared Vector store (Embed takes money) but we didn't play
#     around the point that new users added and deleted every 5 minutes. (Actually, it can be fixed, we can create once
#     Vector store and with new request we will fetch all the users, compare new and deleted with version in Vector
#     store and delete the data about deleted users and add new users).
#   - Limit with top_k (we can set up to 100, but what if the real number of similarity search 100+?)
#   - With some requests works not so perfectly. (Here we can play and add extra chain with LLM that will refactor the
#     user question in a way that will help for Vector search, but it is also not okay in the point that we have
#     changed original user question).
#   - Need to play with balance between top_k and score_threshold
# Benefits are:
#   - Similarity search by context
#   - Any input can be used for search
#   - Costs reduce