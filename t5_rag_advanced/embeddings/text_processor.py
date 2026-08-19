import os
from enum import StrEnum

import psycopg2
from psycopg2.extras import RealDictCursor

from t5_rag_advanced.embeddings.embeddings_client import EmbeddingsClient
from t5_rag_advanced.utils.text import chunk_text


class SearchMode(StrEnum):
    EUCLIDIAN_DISTANCE = "euclidean"  # Euclidean distance (<->)
    COSINE_DISTANCE = "cosine"  # Cosine distance (<=>)


class TextProcessor:
    """Processor for text documents that handles chunking, embedding, storing, and retrieval"""

    def __init__(self, embeddings_client: EmbeddingsClient, db_config: dict):
        self.embeddings_client = embeddings_client
        self.db_config = db_config

    def _get_connection(self):
        """Get database connection"""
        return psycopg2.connect(
            host=self.db_config['host'],
            port=self.db_config['port'],
            database=self.db_config['database'],
            user=self.db_config['user'],
            password=self.db_config['password']
        )

    #TODO:
    # provide method `process_text_file` that will:
    #   - apply file name, chunk size, overlap, dimensions and bool of the table should be truncated
    #   - truncate table with vectors if needed
    #   - load content from file and generate chunks (in `utils.text` present `chunk_text` that will help do that)
    #   - generate embeddings from chunks
    #   - save (insert) embeddings and chunks to DB
    #       hint 1: embeddings should be saved as string list
    #       hint 2: embeddings string list should be casted to vector ({embeddings}::vector)
    def process_text_file(
            self,
            file_path: str,
            chunk_size: int,
            overlap: int,
            dimensions: int,
            truncate_table: bool = False
    ) -> None:
        if truncate_table:
            self._truncate_table()

        with open(file_path, "r", encoding="utf-8") as file:
            content = file.read()

        chunks = chunk_text(content, chunk_size, overlap)
        embeddings = self.embeddings_client.get_embeddings(chunks, dimensions)

        document_name = os.path.basename(file_path)
        for index, chunk in enumerate(chunks):
            self._save_chunk(document_name, chunk, embeddings[index])

    def _truncate_table(self) -> None:
        """Truncate table with vectors"""
        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute("TRUNCATE TABLE vectors")
            connection.commit()
        finally:
            connection.close()

    def _save_chunk(self, document_name: str, text: str, embedding: list[float]) -> None:
        """Save single text chunk with its embedding to DB"""
        embedding_str = str(embedding)

        connection = self._get_connection()
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO vectors (document_name, text, embedding) VALUES (%s, %s, %s::vector)",
                    (document_name, text, embedding_str)
                )
            connection.commit()
        finally:
            connection.close()

    #TODO:
    # provide method `search` that will:
    #   - apply search mode, user request, top k for search, min score threshold and dimensions
    #   - generate embeddings from user request
    #   - search in DB relevant context
    #     hint 1: to search it in DB you need to create just regular select query
    #     hint 2: Euclidean distance `<->`, Cosine distance `<=>`
    #     hint 3: You need to extract `text` from `vectors` table
    #     hint 4: You need to filter distance in WHERE clause
    #     hint 5: To get top k use `limit`
    def search(
            self,
            query: str,
            mode: SearchMode,
            top_k: int,
            min_score: float,
            dimensions: int
    ) -> list[str]:
        embeddings = self.embeddings_client.get_embeddings(query, dimensions)
        query_embedding = str(embeddings[0])

        operator = "<->" if mode == SearchMode.EUCLIDIAN_DISTANCE else "<=>"

        connection = self._get_connection()
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    f"""
                    SELECT text, embedding {operator} %s::vector AS distance
                    FROM vectors
                    WHERE embedding {operator} %s::vector <= %s
                    ORDER BY distance
                    LIMIT %s
                    """,
                    (query_embedding, query_embedding, min_score, top_k)
                )
                rows = cursor.fetchall()
        finally:
            connection.close()

        return [row["text"] for row in rows]


# SELECT text, embedding <->  '[0.23, -0.45, 0.67, ..., 0.12]'::vector AS distance
# FROM vectors
# WHERE embedding <->  '[0.23, -0.45, 0.67, ..., 0.12]'::vector <= {score}
# ORDER BY distance
# LIMIT {top_k};
