import time
from app.config.settings import ProxyConfig, settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ProxyManager:
    """
    Manages a pool of residential proxies with round-robin rotation
    and automatic cooldown on failure.

    - Rotates proxies sequentially to spread load
    - On failure: marks proxy as failed, cools it down for N minutes
    - If all proxies are in cooldown: uses least-recently-failed as fallback
    """

    def __init__(self) -> None:
        self._proxies: list[ProxyConfig] = settings.get_proxy_list()
        self._failed_at: dict[str, float] = {}
        self._current_index: int = 0

        logger.info("ProxyManager initialized with %d proxies", len(self._proxies))

    def get_next(self) -> ProxyConfig:
        available = self._get_available()

        if available:
            proxy = available[self._current_index % len(available)]
            self._current_index += 1
            logger.debug("Using proxy: %s", proxy)
            return proxy

        # All proxies in cooldown — use least-recently-failed
        logger.warning(
            "All %d proxies in cooldown — using least-recently-failed",
            len(self._proxies),
        )
        return min(
            self._proxies,
            key=lambda p: self._failed_at.get(p.server, 0),
        )

    def mark_failed(self, proxy: ProxyConfig) -> None:
        self._failed_at[proxy.server] = time.time()
        logger.warning(
            "Proxy marked failed: %s | %d/%d still available",
            proxy,
            self.available_count,
            self.total_count,
        )

    def mark_success(self, proxy: ProxyConfig) -> None:
        if proxy.server in self._failed_at:
            del self._failed_at[proxy.server]
            logger.debug("Proxy cooldown cleared: %s", proxy)

    @property
    def available_count(self) -> int:
        return len(self._get_available())

    @property
    def total_count(self) -> int:
        return len(self._proxies)

    # ── private ───────────────────────────────────────────────────────────────

    def _get_available(self) -> list[ProxyConfig]:
        now = time.time()
        cooldown = settings.proxy_cooldown_seconds
        return [
            p for p in self._proxies
            if now - self._failed_at.get(p.server, 0) > cooldown
        ]