import json
from app.config.db import get_db_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PostsRepo:
    def save_posts(self, posts: list[dict]) -> int:
        if not posts:
            return 0

        saved = 0
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                for post in posts:
                    cur.execute("""
                        INSERT INTO posts (
                            id, posted_at, post_type, raw_content,
                            analysis_text, shared_article,
                            likes, reposts, replies,
                            caps_ratio, exclamation_count,
                            has_nickname, has_superlative,
                            word_count, signal_strength
                        ) VALUES (
                            %(id)s, %(posted_at)s, %(post_type)s, %(raw_content)s,
                            %(analysis_text)s, %(shared_article)s,
                            %(likes)s, %(reposts)s, %(replies)s,
                            %(caps_ratio)s, %(exclamation_count)s,
                            %(has_nickname)s, %(has_superlative)s,
                            %(word_count)s, %(signal_strength)s
                        )
                        ON CONFLICT (id) DO NOTHING
                    """, {
                        **post,
                        "shared_article": json.dumps(post.get("shared_article")),
                    })
                    saved += cur.rowcount

        logger.info("Saved %d new posts to DB", saved)
        return saved

    def save_local_analysis(self, post_id: str, analysis: dict) -> None:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO local_analyses (
                        post_id, sentiment, top_emotions, entities, zeroshot_mood
                    ) VALUES (
                        %(post_id)s, %(sentiment)s, %(top_emotions)s,
                        %(entities)s, %(zeroshot_mood)s
                    )
                    ON CONFLICT (post_id) DO NOTHING
                """, {
                    "post_id": post_id,
                    "sentiment": json.dumps(analysis.get("sentiment")),
                    "top_emotions": json.dumps(analysis.get("top_emotions")),
                    "entities": json.dumps(analysis.get("entities")),
                    "zeroshot_mood": json.dumps(analysis.get("zeroshot_mood")),
                })
