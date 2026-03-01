import asyncio
from datetime import datetime, timezone

from app.ingestion.fetcher import TruthSocialFetcher
from app.ingestion.parser import PostParser
from app.services.local_analyzer import LocalAnalyzer
from app.services.batch_summarizer import BatchSummarizer
from app.services.mood_synthesizer import MoodSynthesizer
from app.rag.mood_retriever import MoodRetriever
from app.repositories.posts_repo import PostsRepo
from app.repositories.mood_state_repo import MoodStateRepo
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FetchCycleService:
    """
    Orchestrates one complete fetch-and-analyze cycle.

    Flow:
        1. Fetch new posts from Truth Social
        2. Parse and clean posts
        3. Run local HuggingFace models (free, no API cost)
        4. Summarize new batch with Sonnet (cheap)
        5. Retrieve similar past moods via RAG
        6. Synthesize updated mood state with Opus (one call per cycle)
        7. Persist everything to DB
        8. Store snapshot in RAG if mood shifted
    """

    def __init__(self) -> None:
        self._fetcher = TruthSocialFetcher()
        self._parser = PostParser()
        self._local_analyzer = LocalAnalyzer()
        self._batch_summarizer = BatchSummarizer()
        self._mood_synthesizer = MoodSynthesizer()
        self._mood_retriever = MoodRetriever()
        self._posts_repo = PostsRepo()
        self._mood_state_repo = MoodStateRepo()

    async def run(self) -> dict:
        logger.info("--- Fetch cycle starting ---")

        state = self._mood_state_repo.get_today_state()
        since_id = state.get("last_fetch_cursor")

        logger.info("Cursor loaded: %s", since_id)  # add this

        # Fetch world context and posts concurrently
        world_context, raw_posts = await asyncio.gather(
            self._get_world_context(),
            self._fetcher.fetch_new_posts(since_id),
        )

        logger.debug("RAW Posts %d", len(raw_posts))
        logger.debug("World context %s", world_context)

        if world_context:
            logger.info("World context fetched: %d", len(world_context))

        if not raw_posts:
            logger.info("No new posts — cycle skipped")
            return state

        parsed_posts = self._parser.parse_many(raw_posts)
        parsed_posts = self._local_analyzer.analyze_many(parsed_posts)
        print("parsed_posts", parsed_posts)

        self._posts_repo.save_posts(parsed_posts)

        batch_index = len(state.get("context_summaries", []))
        new_batch_summary = await self._batch_summarizer.summarize_batch(
            parsed_posts, batch_index, world_context=world_context
        )
        print("new_batch_summary", new_batch_summary)

        rag_context = self._mood_retriever.retrieve_similar(
            themes=new_batch_summary.get("key_themes", []),
            current_mood=state["current_mood"]["label"],
        )
        
        print("rag_context", rag_context)

        mood_before = state["current_mood"]["label"]
        synthesis = await self._mood_synthesizer.synthesize(
            state, new_batch_summary, parsed_posts, rag_context, world_context=world_context
        )

        updated_state = self._build_updated_state(
            state, parsed_posts, new_batch_summary, synthesis
        )

        self._mood_state_repo.save_state(updated_state)
        self._mood_state_repo.log_cycle({
            "date": updated_state["date"],
            "new_tweets_count": len(parsed_posts),
            "mood_before": mood_before,
            "mood_after": synthesis.get("current_mood"),
            "shift_detected": synthesis.get("shift_detected", False),
            "cycle_output": synthesis,
        })

        if synthesis.get("shift_detected"):
            self._mood_retriever.store_snapshot({
                "date": updated_state["date"],
                "mood": synthesis.get("current_mood"),
                "intensity": synthesis.get("intensity"),
                "key_themes": synthesis.get("key_themes", []),
                "analyst_note": synthesis.get("analyst_note", ""),
            })
            logger.info(
                "Mood shift detected: %s -> %s",
                mood_before,
                synthesis.get("current_mood"),
            )

        logger.info("--- Fetch cycle complete ---")
        return updated_state

    async def close(self) -> None:
        await self._fetcher.close()

    # ── private ───────────────────────────────────────────────────────────────

    def _build_updated_state(
        self,
        state: dict,
        new_posts: list[dict],
        batch_summary: dict,
        synthesis: dict,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        acc = state.get("accumulated", {})
        total_so_far = acc.get("total_posts", 0)
        total_new = len(new_posts)
        total_all = total_so_far + total_new

        new_caps_avg = sum(p["caps_ratio"] for p in new_posts) / max(total_new, 1)
        updated_caps_avg = (
            (acc.get("caps_ratio_avg", 0.0) * total_so_far + new_caps_avg * total_new)
            / max(total_all, 1)
        )

        # Truth Social returns newest post first — so index 0 is the most recent
        # since_id should be the newest post ID so next fetch only gets newer ones
        newest_post_id = new_posts[0]["id"] if new_posts else state.get("last_fetch_cursor")
        print("new_posts", new_posts[0])
        print("newest_post_id", newest_post_id)

        logger.info("Saving cursor: %s", newest_post_id)  # add this

        return {
            **state,
            "last_fetch_cursor": newest_post_id,
            "accumulated": {
                "total_posts": total_all,
                "caps_ratio_avg": round(updated_caps_avg, 3),
                "posts_per_hour": acc.get("posts_per_hour", 0.0),
                "peak_posts_per_hour": acc.get("peak_posts_per_hour", 0.0),
            },
            "current_mood": {
                "label": synthesis.get("current_mood"),
                "intensity": synthesis.get("intensity"),
                "confidence": synthesis.get("confidence"),
                "since": synthesis.get("mood_sustained_since", now),
            },
            "context_summaries": [
                *state.get("context_summaries", []),
                batch_summary,
            ],
            "mood_timeline": [
                *state.get("mood_timeline", []),
                {
                    "time": now,
                    "mood": synthesis.get("current_mood"),
                    "intensity": synthesis.get("intensity"),
                    "shift_detected": synthesis.get("shift_detected", False),
                },
            ],
        }

    async def _get_world_context(self) -> str:
        """Get current news headlines relevant to Trump using Claude with web search."""
        try:
            import anthropic
            from app.config.settings import settings

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            response = client.messages.create(
                model=settings.sonnet_model,
                max_tokens=500,
                tools=[{"type": "web_search_20250305", "name": "web_search"}],
                messages=[{
                    "role": "user",
                    "content": (
                        "Give me a brief 5-bullet summary of the most important "
                        "political, legal, economic, and market news from the last "
                        "24 hours that Donald Trump would likely be reacting to. "
                        "Focus on: court cases, political rivals, market moves, "
                        "media coverage of him, and major policy developments. "
                        "Be concise — one line per bullet."
                    ),
                }],
            )
            text = " ".join(
                block.text for block in response.content
                if hasattr(block, "text")
            )
            return text.strip()
        except Exception as exc:
            logger.warning("World context fetch failed: %s", exc)
            return ""