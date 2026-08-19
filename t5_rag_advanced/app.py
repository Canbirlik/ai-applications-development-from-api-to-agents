import os

from commons.constants import OPENAI_API_KEY, OPENAI_EMBEDDINGS_ENDPOINT, OPENAI_CHAT_COMPLETIONS_ENDPOINT
from commons.models.conversation import Conversation
from commons.models.message import Message
from commons.models.role import Role
from t5_rag_advanced.chat.chat_completion_client import ChatCompletionClient
from t5_rag_advanced.embeddings.embeddings_client import EmbeddingsClient
from t5_rag_advanced.embeddings.text_processor import TextProcessor, SearchMode

#TODO:
# Create system prompt with info that it is RAG powered assistant.
# Explain user message structure (firstly will be provided RAG context and the user question).
# Provide instructions that LLM should use RAG Context when answer on User Question, will restrict LLM to answer
# questions that are not related microwave usage, not related to context or out of history scope
SYSTEM_PROMPT = """You are a RAG (Retrieval-Augmented Generation) powered assistant that helps users with
questions about a microwave oven, using ONLY the information found in the manual.

Each user message is structured in two sections:
- RAG CONTEXT: relevant excerpts retrieved from the microwave manual for the current question
- USER QUESTION: the actual question asked by the user

Rules:
- Base your answer strictly on the RAG CONTEXT provided in the user's message.
- If the RAG CONTEXT does not contain enough information to answer the USER QUESTION, say that you don't
  know based on the provided manual. Do not use any outside knowledge.
- Do not answer questions that are unrelated to the microwave manual, not present in the RAG CONTEXT, or
  outside the scope of this conversation's history.
"""

#TODO:
# Provide structured system prompt, with RAG Context and User Question sections.
USER_PROMPT = """##RAG CONTEXT:
{context}


##USER QUESTION:
{query}"""

#TODO:
# - create embeddings client with 'text-embedding-3-small' model, OPENAI_EMBEDDINGS_ENDPOINT endpoint and OPENAI_API_KEY
# - create chat completion client with 'gpt-5.2' model, OPENAI_CHAT_COMPLETIONS_ENDPOINT endpoint and OPENAI_API_KEY
# - create text processor, DB config: {'host': 'localhost','port': 5433,'database': 'vectordb','user': 'postgres','password': 'postgres'}
# ---
# Create method that will run console chat with such steps:
# - get user input from console
# - retrieve context
# - perform augmentation
# - perform generation
# - it should run in `while` loop (since it is console chat)
def run_chat(text_processor: TextProcessor, chat_client: ChatCompletionClient) -> None:
    conversation = Conversation()
    conversation.add_message(Message(Role.SYSTEM, SYSTEM_PROMPT))

    print("Welcome to the Microwave Manual Assistant! Ask a question or type 'exit' to quit.")
    while True:
        query = input("> ").strip()
        if query.lower() == "exit":
            print("Goodbye!")
            break
        if not query:
            continue

        # Retrieval
        context_chunks = text_processor.search(
            query=query,
            mode=SearchMode.COSINE_DISTANCE,
            top_k=4,
            min_score=0.5,
            dimensions=384
        )
        context = "\n\n".join(context_chunks)

        # Augmentation
        augmented_prompt = USER_PROMPT.format(context=context, query=query)
        conversation.add_message(Message(Role.USER, augmented_prompt))

        # Generation
        response = chat_client.get_completion(conversation.get_messages())
        conversation.add_message(response)

        print(response.content)


def main() -> None:
    embeddings_client = EmbeddingsClient(
        endpoint=OPENAI_EMBEDDINGS_ENDPOINT,
        model_name="text-embedding-3-small",
        api_key=OPENAI_API_KEY
    )
    chat_client = ChatCompletionClient(
        endpoint=OPENAI_CHAT_COMPLETIONS_ENDPOINT,
        model_name="gpt-5.2",
        api_key=OPENAI_API_KEY
    )
    text_processor = TextProcessor(
        embeddings_client=embeddings_client,
        db_config={
            "host": "localhost",
            "port": 5433,
            "database": "vectordb",
            "user": "postgres",
            "password": "postgres"
        }
    )

    manual_path = os.path.join(os.path.dirname(__file__), "embeddings", "microwave_manual.txt")
    text_processor.process_text_file(
        file_path=manual_path,
        chunk_size=500,
        overlap=50,
        dimensions=384,
        truncate_table=True
    )

    run_chat(text_processor, chat_client)


# TODO:
#  PAY ATTENTION THAT YOU NEED TO RUN Postgres DB ON THE 5433 WITH PGVECTOR EXTENSION!
#  RUN docker-compose.yml
main()
