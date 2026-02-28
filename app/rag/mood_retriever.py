from langchain_community.vectorstores.pgvector import PGVector
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
        self._store: PGVector | None = None

    def retrieve_similar(
        self,
        themes: list[str],
        current_mood: str,
        k: int = 5,
    ) -> list[str]:
        query = f"mood: {current_mood}, themes: {', '.join(themes)}"

        try:
            results = self._get_store().similarity_search(query, k=k)
            return [r.page_content for r in results]
        except Exception as exc:
            logger.warning("RAG retrieval failed: %s", exc)
            # Reset store so next call gets a fresh connection
            self._store = None
            return []

    def store_snapshot(self, snapshot: dict) -> None:
        try:
            text = self._snapshot_to_text(snapshot)
            self._get_store().add_texts(texts=[text], metadatas=[snapshot])
            logger.debug("Stored mood snapshot for %s", snapshot.get("date"))
        except Exception as exc:
            logger.warning("RAG store failed: %s", exc)
            self._store = None

    # ── private ───────────────────────────────────────────────────────────────

    def _get_store(self) -> PGVector:
        if self._store is None:
            logger.info("Loading local embedding model (first use)...")
            embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
            self._store = PGVector(
                connection_string=settings.database_url,
                embedding_function=embeddings,
                collection_name="mood_history",
            )
        return self._store

    def _snapshot_to_text(self, snapshot: dict) -> str:
        return (
            f"Date: {snapshot.get('date')} | "
            f"Mood: {snapshot.get('mood')} ({snapshot.get('intensity')}) | "
            f"Themes: {', '.join(snapshot.get('key_themes', []))} | "
            f"Note: {snapshot.get('analyst_note', '')}"
        )
