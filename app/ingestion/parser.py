from datetime import datetime
from bs4 import BeautifulSoup
from app.utils.constants import (
    PostType,
    SignalStrength,
    NICKNAME_PATTERN,
    SUPERLATIVE_PATTERN,
    URL_PATTERN,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PostParser:
    """
    Converts raw Truth Social API responses into clean, analysis-ready dicts.
    Also extracts local signals (caps ratio, nicknames etc.) — zero LLM cost.
    """

    def parse(self, raw: dict) -> dict:
        post_type = self._detect_type(raw)
        clean_content = self._clean_content(raw.get("content", ""))
        card = raw.get("card")

        return {
            "id": raw["id"],
            "posted_at": self._parse_datetime(raw["created_at"]),
            "post_type": post_type,
            "raw_content": clean_content,
            "analysis_text": self._build_analysis_text(post_type, clean_content, card),
            "shared_article": self._extract_card(card),
            "likes": raw.get("favourites_count", 0),
            "reposts": raw.get("reblogs_count", 0),
            "replies": raw.get("replies_count", 0),
            **self._extract_signals(clean_content, post_type),
            "local_analysis": None,  # populated later by LocalAnalyzer
        }

    def parse_many(self, raw_posts: list[dict]) -> list[dict]:
        results = []
        for raw in raw_posts:
            try:
                results.append(self.parse(raw))
            except Exception as exc:
                logger.warning("Failed to parse post %s: %s", raw.get("id"), exc)
        return results

    # ── private ───────────────────────────────────────────────────────────────

    def _detect_type(self, raw: dict) -> str:
        if raw.get("reblog"):
            return PostType.RETRUTH
        if raw.get("card") and raw["card"].get("url"):
            return PostType.LINK_SHARE
        return PostType.ORIGINAL

    def _clean_content(self, html: str) -> str:
        text = BeautifulSoup(html, "html.parser").get_text()
        return URL_PATTERN.sub("", text).strip()

    def _build_analysis_text(
        self, post_type: str, content: str, card: dict | None
    ) -> str:
        if post_type == PostType.ORIGINAL:
            return content

        if post_type == PostType.LINK_SHARE and card:
            parts = []
            if content:
                parts.append(f'His framing: "{content}"')
            if card.get("title"):
                parts.append(f'Article shared: "{card["title"]}"')
            if card.get("description"):
                parts.append(f'Article context: "{card["description"]}"')
            return "\n".join(parts)

        if post_type == PostType.RETRUTH:
            return f"[Retruthed] {content}"

        return content

    def _extract_card(self, card: dict | None) -> dict | None:
        if not card:
            return None
        return {
            "title": card.get("title"),
            "description": card.get("description"),
            "url": card.get("url"),
            "source": card.get("provider_name"),
        }

    def _extract_signals(self, content: str, post_type: str) -> dict:
        if not content or post_type == PostType.RETRUTH:
            return {
                "caps_ratio": 0.0,
                "exclamation_count": 0,
                "has_nickname": False,
                "has_superlative": False,
                "word_count": 0,
                "signal_strength": SignalStrength.LOW,
            }

        words = content.split()
        upper_words = [w for w in words if w == w.upper() and len(w) > 2]

        if post_type == PostType.ORIGINAL and len(words) > 10:
            strength = SignalStrength.HIGH
        elif post_type == PostType.LINK_SHARE:
            strength = SignalStrength.MEDIUM
        else:
            strength = SignalStrength.LOW

        return {
            "caps_ratio": round(len(upper_words) / max(len(words), 1), 3),
            "exclamation_count": content.count("!"),
            "has_nickname": bool(NICKNAME_PATTERN.search(content)),
            "has_superlative": bool(SUPERLATIVE_PATTERN.search(content)),
            "word_count": len(words),
            "signal_strength": strength,
        }

    def _parse_datetime(self, value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
