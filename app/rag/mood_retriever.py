from langchain_postgres.vectorstores import PGVector
from langchain_huggingface import HuggingFaceEmbeddings

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MoodRetriever:
    """
    Stores mood snapshots as vector embeddings in PostgreSQL via pgvector.
    Uses a free local embedding model (MiniLM) — no API cost.

    On each synthesis cycle, retrieves historically similar mood contexts
    so the LLM receives relevant past patterns without needing full history.
    """

    def __init__(self) -> None:
        # _embeddings MUST be assigned before _store
        self._embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model,
        )
        self._store = PGVector(
            embeddings=self._embeddings,
            collection_name="mood_snapshots",
            connection=settings.database_url,
            use_jsonb=True,
        )



    def retrieve_similar(
        self,
        themes: list[str],
        current_mood: str,
        k: int = 5,
    ) -> list[str]:
        query = f"mood: {current_mood}, themes: {', '.join(themes)}"
        try:
            results = self._store.similarity_search(query, k=k)
            return [r.page_content for r in results]
        except Exception as exc:
            logger.warning("RAG retrieval failed: %s", exc)
            self._store = None
            return []

    def store_snapshot(self, snapshot: dict) -> None:
        try:
            text = self._snapshot_to_text(snapshot)
            self._store.add_texts(texts=[text], metadatas=[snapshot])
            logger.debug("Stored mood snapshot for %s", snapshot.get("date"))
        except Exception as exc:
            logger.warning("RAG store failed: %s", exc)
            self._store = None

    def _get_store(self) -> PGVector:
        if self._store is None:
            self._store = PGVector(
                embeddings=self._embeddings,
                collection_name="mood_snapshots",
                connection=settings.database_url,
                use_jsonb=True,
            )
        return self._store

    def _snapshot_to_text(self, snapshot: dict) -> str:
        return (
            f"Date: {snapshot.get('date')} | "
            f"Mood: {snapshot.get('mood')} ({snapshot.get('intensity')}) | "
            f"Themes: {', '.join(snapshot.get('key_themes', []))} | "
            f"{snapshot.get('analyst_note', '')}"
        )
