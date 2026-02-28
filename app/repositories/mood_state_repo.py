import json
from datetime import date
from app.config.db import get_db_connection
from app.utils.constants import MoodLabel, Intensity
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MoodStateRepo:
    def get_today_state(self) -> dict:
        today = date.today().isoformat()

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT raw_state FROM daily_mood_state WHERE date = %s",
                    (today,),
                )
                row = cur.fetchone()

        if row:
            raw = row["raw_state"]
            state = raw if isinstance(raw, dict) else json.loads(raw)

            # If the state is from today, use it as-is
            # cursor from yesterday would pull old posts — always start fresh each day
            if state.get("date") == today:
                return state

        # Fresh state for today — no cursor, clean slate
        return self._empty_state(today)

    def save_state(self, state: dict) -> None:
        mood = state["current_mood"]

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO daily_mood_state (
                        date, last_updated, last_fetch_cursor,
                        current_mood, current_intensity, current_confidence,
                        accumulated_stats, context_summaries,
                        mood_timeline, raw_state
                    ) VALUES (
                        %(date)s, NOW(), %(cursor)s,
                        %(mood_label)s, %(intensity)s, %(confidence)s,
                        %(accumulated)s, %(summaries)s,
                        %(timeline)s, %(raw)s
                    )
                    ON CONFLICT (date) DO UPDATE SET
                        last_updated        = NOW(),
                        last_fetch_cursor   = EXCLUDED.last_fetch_cursor,
                        current_mood        = EXCLUDED.current_mood,
                        current_intensity   = EXCLUDED.current_intensity,
                        current_confidence  = EXCLUDED.current_confidence,
                        accumulated_stats   = EXCLUDED.accumulated_stats,
                        context_summaries   = EXCLUDED.context_summaries,
                        mood_timeline       = EXCLUDED.mood_timeline,
                        raw_state           = EXCLUDED.raw_state
                """, {
                    "date": state["date"],
                    "cursor": state.get("last_fetch_cursor"),
                    "mood_label": mood["label"],
                    "intensity": mood["intensity"],
                    "confidence": mood["confidence"],
                    "accumulated": json.dumps(state["accumulated"]),
                    "summaries": json.dumps(state["context_summaries"]),
                    "timeline": json.dumps(state["mood_timeline"]),
                    "raw": json.dumps(state),
                })

        logger.info(
            "State saved — mood: %s (%s) confidence: %.2f",
            mood["label"],
            mood["intensity"],
            mood["confidence"],
        )

    def log_cycle(self, cycle_log: dict) -> None:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO mood_cycle_log (
                        date, ran_at, new_tweets_count,
                        mood_before, mood_after,
                        shift_detected, cycle_output
                    ) VALUES (
                        %(date)s, NOW(), %(new_tweets_count)s,
                        %(mood_before)s, %(mood_after)s,
                        %(shift_detected)s, %(cycle_output)s
                    )
                """, {
                    **cycle_log,
                    "cycle_output": json.dumps(cycle_log.get("cycle_output")),
                })

    # ── private ───────────────────────────────────────────────────────────────

    def _empty_state(self, today: str) -> dict:
        return {
            "date": today,
            "last_fetch_cursor": None,
            "accumulated": {
                "total_posts": 0,
                "caps_ratio_avg": 0.0,
                "posts_per_hour": 0.0,
                "peak_posts_per_hour": 0.0,
            },
            "current_mood": {
                "label": MoodLabel.UNKNOWN,
                "intensity": Intensity.LOW,
                "confidence": 0.0,
                "since": today,
            },
            "context_summaries": [],
            "mood_timeline": [],
        }
