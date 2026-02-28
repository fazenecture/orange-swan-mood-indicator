import json
from fastapi import APIRouter, HTTPException
from app.config.db import get_db_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/mood")


class MoodRouter:
    def __init__(self) -> None:
        router.add_api_route("/today", self.get_today_mood, methods=["GET"])
        router.add_api_route("/today/timeline", self.get_today_timeline, methods=["GET"])

    def get_today_mood(self) -> dict:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        date,
                        current_mood,
                        current_intensity,
                        current_confidence,
                        context_summaries,
                        last_updated
                    FROM daily_mood_state
                    WHERE date = CURRENT_DATE
                """)
                row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=400, detail="No mood data for today yet")

        return {
            "date": str(row["date"]),
            "mood": row["current_mood"],
            "intensity": row["current_intensity"],
            "confidence": row["current_confidence"],
            "last_updated": str(row["last_updated"]),
            "context_summaries": row["context_summaries"],
        }

    def get_today_timeline(self) -> dict:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        date,
                        mood_timeline,
                        last_updated
                    FROM daily_mood_state
                    WHERE date = CURRENT_DATE
                """)
                row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="No mood data for today yet")

        timeline = row["mood_timeline"]
        if isinstance(timeline, str):
            timeline = json.loads(timeline)

        return {
            "date": str(row["date"]),
            "last_updated": str(row["last_updated"]),
            "timeline": timeline,
        }


MoodRouter()