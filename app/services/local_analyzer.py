from functools import lru_cache
from app.utils.constants import ZEROSHOT_MOOD_CANDIDATES
from app.utils.logger import get_logger

logger = get_logger(__name__)
MAX_TOKENS = 512
CHARS_PER_TOKEN = 4

class LocalAnalyzer:
    """
    Runs HuggingFace models locally — completely free, no API cost.
    Models are lazy-loaded on first use and cached for the process lifetime.

    Runs BEFORE any LLM call to pre-populate signals cheaply.
    Results are passed into the LLM prompt as structured context.
    """

    def analyze(self, text: str) -> dict | None:
        if not text or len(text.strip()) < 10:
            return None

        text = self._truncate(text)

        try:
            return {
                "sentiment": self._run_sentiment(text),
                "top_emotions": self._run_emotions(text),
                "entities": self._run_ner(text),
                "zeroshot_mood": self._run_zeroshot(text),
            }
        except Exception as exc:
            logger.warning("Local analysis failed: %s", exc)
            return None

    def _truncate(self, text: str) -> str:
        max_chars = MAX_TOKENS * CHARS_PER_TOKEN
        return text[:max_chars] if len(text) > max_chars else text

    def analyze_many(self, posts: list[dict]) -> list[dict]:
        for post in posts:
            post["local_analysis"] = self.analyze(post.get("analysis_text", ""))
        return posts

    # ── private (lazy-loaded models) ──────────────────────────────────────────

    def _run_sentiment(self, text: str) -> dict:
        result = self._sentiment_model()(text)[0]
        return {"label": result["label"], "score": round(result["score"], 3)}

    def _run_emotions(self, text: str) -> list[dict]:
        results = self._emotion_model()(text)
        return [
            {"label": e["label"], "score": round(e["score"], 3)}
            for e in results[0]
        ]

    def _run_ner(self, text: str) -> list[dict]:
        results = self._ner_model()(text)
        return [
            {"text": e["word"], "type": e["entity_group"]}
            for e in results
            if e["score"] > 0.8
        ]

    def _run_zeroshot(self, text: str) -> dict:
        result = self._zeroshot_model()(text, ZEROSHOT_MOOD_CANDIDATES)
        return {"label": result["labels"][0], "score": round(result["scores"][0], 3)}

    @lru_cache(maxsize=1)
    def _sentiment_model(self):
        from transformers import pipeline
        logger.info("Loading sentiment model (first use)...")
        return pipeline(
            "text-classification",
            model="cardiffnlp/twitter-roberta-base-sentiment-latest",
        )

    @lru_cache(maxsize=1)
    def _emotion_model(self):
        from transformers import pipeline
        logger.info("Loading emotion model (first use)...")
        return pipeline("text-classification", model="SamLowe/roberta-base-go_emotions", top_k=3)

    @lru_cache(maxsize=1)
    def _ner_model(self):
        from transformers import pipeline
        logger.info("Loading NER model (first use)...")
        return pipeline("ner", model="dslim/bert-base-NER", aggregation_strategy="simple")

    @lru_cache(maxsize=1)
    def _zeroshot_model(self):
        from transformers import pipeline
        logger.info("Loading zero-shot classifier (first use)...")
        return pipeline("zero-shot-classification", model="facebook/bart-large-mnli")
