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
        router.add_api_route("/history", self.get_mood_history, methods=["GET"])
        router.add_api_route("/market-overlay", self.get_market_overlay, methods=["GET"])

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
    

    def get_mood_history(self, days: int = 7) -> dict:
        intensity_map = {"low": 1, "medium": 2, "high": 3, "frenetic": 4}

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        date,
                        current_mood,
                        current_intensity,
                        current_confidence,
                        last_updated
                    FROM daily_mood_state
                    WHERE date >= CURRENT_DATE - INTERVAL '%d days'
                    ORDER BY date ASC
                """ % days)
                rows = cur.fetchall()

        return {
            "days": days,
            "history": [
                {
                    "date": str(row["date"]),
                    "mood": row["current_mood"],
                    "intensity": row["current_intensity"],
                    "intensity_score": intensity_map.get(row["current_intensity"], 0),
                    "confidence": row["current_confidence"],
                    "last_updated": str(row["last_updated"]),
                }
                for row in rows
            ],
        }


    def get_market_overlay(self, days: int = 7) -> dict:
        import httpx
        from datetime import datetime, timedelta

        intensity_map = {"low": 1, "medium": 2, "high": 3, "frenetic": 4}

        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT date, current_mood, current_intensity
                    FROM daily_mood_state
                    WHERE date >= CURRENT_DATE - INTERVAL '%d days'
                    ORDER BY date ASC
                """ % days)
                mood_rows = cur.fetchall()

        end = datetime.now()
        start = end - timedelta(days=days + 3)
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/%5EGSPC"
            f"?interval=1d"
            f"&period1={int(start.timestamp())}"
            f"&period2={int(end.timestamp())}"
        )

        # Build market lookup by date
        market_by_date = {}
        market = []
        try:
            resp = httpx.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
            data = resp.json()
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            closes = result["indicators"]["quote"][0]["close"]
            for ts, close in zip(timestamps, closes):
                if close is not None:
                    date_str = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                    market_by_date[date_str] = round(close, 2)

            # Fill gaps — for each mood date that has no market data
            # (weekend, holiday) carry forward the last known close price
            mood_dates = sorted([str(r["date"]) for r in mood_rows])
            last_known_close = None
            for date in mood_dates:
                if date in market_by_date:
                    last_known_close = market_by_date[date]
                elif last_known_close is not None:
                    # Carry forward last known price for this date
                    market_by_date[date] = last_known_close

            # Rebuild market list in date order covering all mood dates
            market = [
                {"date": date, "close": market_by_date[date]}
                for date in mood_dates
                if date in market_by_date
            ]

        except Exception as exc:
            logger.warning("Market data fetch failed: %s", exc)

        return {
            "mood": [
                {
                    "date": str(r["date"]),
                    "mood": r["current_mood"],
                    "intensity_score": intensity_map.get(r["current_intensity"], 0),
                }
                for r in mood_rows
            ],
            "market": market,
        }


MoodRouter()