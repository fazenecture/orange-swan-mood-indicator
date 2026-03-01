import asyncio
import random
import time
from datetime import date, timezone, datetime
from playwright.async_api import async_playwright, BrowserContext
from app.config.settings import settings
from app.utils.logger import get_logger
from app.ingestion.proxy_manager import ProxyManager
from app.utils.constants import USER_AGENTS
from app.config.settings import ProxyConfig
import zoneinfo

logger = get_logger(__name__)


class TruthSocialFetcher:
    """
    Fetches posts from Truth Social using a persistent Playwright browser
    session routed through a residential proxy.

    Session is reused across cycles and only recreated when it expires
    or errors — avoids spinning up a new browser every 5 minutes.
    """

    def __init__(self) -> None:
        self._context: BrowserContext | None = None
        self._session_created_at: float | None = None
        self._current_proxy: ProxyConfig | None = None
        self._playwright = None
        self._proxy_manager = ProxyManager()


    async def fetch_new_posts(self, since_id: str | None = None) -> list[dict]:
        return await self._fetch_with_retry(since_id)

    async def close(self) -> None:
        try:
            if self._context:
                await self._context.browser.close()
        except Exception:
            pass
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception:
            pass


    # ── private ───────────────────────────────────────────────────────────────

    async def _fetch_with_retry(
        self, since_id: str | None, attempts: int = 3
    ) -> list[dict]:
        for attempt in range(attempts):
            try:
                return await self._do_fetch(since_id)
            except Exception as exc:
                logger.warning("Fetch attempt %d/%d failed: %s", attempt + 1, attempts, exc)
                self._context = None  # force session recreate
                if attempt < attempts - 1:
                    await asyncio.sleep(5)

        logger.error("All %d fetch attempts exhausted", attempts)
        return []

    async def _do_fetch(self, since_id: str | None) -> list[dict]:
        context = await self._get_or_create_session()
        page = await context.new_page()
        api_response = None

        async def handle_response(response):
            nonlocal api_response
            # Intercept the page's natural statuses call — ignore pinned/media variants
            print("response.url", response.url)
            print("response.status", response.status)
            
            if (
                f"/accounts/{settings.account_id}/statuses" in response.url
                and "pinned=true" not in response.url
                and "only_media=true" not in response.url
                and response.status == 200
                and api_response is None  # take the first match only
            ):
                try:
                    data = await response.json()
                    if isinstance(data, list) and len(data) > 0:
                        api_response = data
                        logger.debug(
                            "Intercepted %d posts from: %s",
                            len(data),
                            response.url,
                        )
                except Exception as exc:
                    logger.warning("Failed to parse intercepted response: %s", exc)

        try:
            page.on("response", handle_response)
            await page.goto(settings.profile_url, wait_until="networkidle")
            await page.wait_for_timeout(3000)

            if api_response is None:
                logger.warning("No statuses response intercepted during page load")
                return []

            # The page returns its own set of posts — filter to only ones newer than our cursor
            if since_id:
                api_response = [
                    p for p in api_response
                    if int(p["id"]) > int(since_id)
                ]
                logger.debug(
                    "After since_id filter: %d posts newer than %s",
                    len(api_response),
                    since_id,
                )

            logger.info(
                "Fetched %d new posts via %s",
                len(api_response),
                self._current_proxy,
            )
            return api_response

        finally:
            page.remove_listener("response", handle_response)
            await page.close()

    async def _get_or_create_session(self) -> BrowserContext:
        session_expired = (
            self._session_created_at is None
            or (time.time() - self._session_created_at) > settings.session_max_age_seconds
        )

        if self._context is None or session_expired:
            await self._create_session()

        return self._context  # type: ignore[return-value]


    async def _create_session(self) -> None:
        proxy = self._proxy_manager.get_next()
        self._current_proxy = proxy

        logger.info(
            "Creating browser session | proxy: %s | pool: %d/%d available",
            proxy,
            self._proxy_manager.available_count,
            self._proxy_manager.total_count,
        )

        if self._context:
            try:
                await self._context.browser.close()
            except Exception:
                pass

        if self._playwright is None:
            self._playwright = await async_playwright().start()

        browser = await self._playwright.chromium.launch(
            headless=True,
            proxy=proxy.playwright_proxy,
        )

        self._context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport=random.choice([
                {"width": 1280, "height": 800},
                {"width": 1440, "height": 900},
                {"width": 1920, "height": 1080},
            ]),
            locale="en-US",
            timezone_id="America/New_York",
        )

        # Block all non-essential requests — images, media, fonts, ads, tracking
        await self._context.route(
            "**/*",
            lambda route: route.abort()
            if route.request.resource_type in {
                "image",
                "media",
                "font",
                "stylesheet",
                "svg",
            }
            or any(
                domain in route.request.url
                for domain in [
                    "static-assets-1.truthsocial.com",  # media CDN
                    "1a-1791.com",                       # video CDN
                    "sentry.io",                         # error tracking
                    "cookie-script.com",                 # cookie consent
                    "googletagmanager.com",              # analytics
                    "google-analytics.com",              # analytics
                    "innovid.js",                        # ad tracking
                    "truth/ads",                         # truth social ads
                    "ads?",                              # ad requests
                    "ads/impression",                    # ad impressions
                ]
            )
            else route.continue_()
        )

        # Visit profile page to get Cloudflare cookies
        page = await self._context.new_page()
        await page.goto(settings.profile_url, wait_until="networkidle")
        await page.wait_for_timeout(2500)
        await page.close()

        self._session_created_at = time.time()
        logger.info("Browser session ready via %s", proxy)

    def _build_api_url(self, since_id: str | None) -> str:
        params: dict[str, str] = {
            "exclude_replies": "true",
            "only_replies": "false",
            "with_muted": "true",
            "limit": "40",
        }
        # Only fetch posts newer than our last cursor
        # If no cursor yet today, we still only want today's posts
        if since_id:
            params["since_id"] = since_id

        query = "&".join(f"{k}={v}" for k, v in params.items())
        return (
            f"{settings.api_base_url}/accounts"
            f"/{settings.account_id}/statuses?{query}"
        )

    def _filter_today(self, posts: list[dict]) -> list[dict]:
        """Convert UTC timestamps to local timezone before comparing to today."""
        local_tz = zoneinfo.ZoneInfo("Asia/Kolkata")  # change to your timezone
        today = date.today()

        filtered = []
        for p in posts:
            created_at = p.get("created_at", "")
            if not created_at:
                continue
            try:
                # Parse UTC timestamp and convert to local time
                utc_dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                local_dt = utc_dt.astimezone(local_tz)
                print("local_dt",  local_dt, utc_dt)

                if local_dt.date() == today:
                    filtered.append(p)
                else:
                    logger.debug(
                        "Dropped post — UTC: %s | Local: %s | Today: %s",
                        created_at,
                        local_dt.date(),
                        today,
                    )
            except Exception as exc:
                logger.warning("Could not parse created_at '%s': %s", created_at, exc)

        dropped = len(posts) - len(filtered)
        if dropped:
            logger.debug("Dropped %d posts from previous days", dropped)

        return filtered
