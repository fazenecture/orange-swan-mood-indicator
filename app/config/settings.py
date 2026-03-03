from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from dataclasses import dataclass


@dataclass(frozen=True)
class ProxyConfig:
    server: str
    username: str
    password: str

    @property
    def playwright_proxy(self) -> dict:
        return {
            "server": f"http://{self.server}",
            "username": self.username,
            "password": self.password,
        }

    def __str__(self) -> str:
        return f"{self.server} ({self.username})"


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(..., env="DATABASE_URL")

    # ── Anthropic ─────────────────────────────────────────────────────────────
    anthropic_api_key: str = Field(..., env="ANTHROPIC_API_KEY")

    # ── OpenAI ───────────────────────────────────────────────────────────────
    openai_api_key: str = Field("", env="OPENAI_API_KEY")
    openai_sonnet_equivalent: str = Field("gpt-4o-mini", env="OPENAI_SONNET_MODEL")
    openai_opus_equivalent: str = Field("gpt-4o", env="OPENAI_OPUS_MODEL")


    # ── Proxies ───────────────────────────────────────────────────────────────
    proxies: str = Field(..., env="PROXIES")

    # ── Truth Social ──────────────────────────────────────────────────────────
    account_id: str = "107780257626128497"
    api_base_url: str = "https://truthsocial.com/api/v1"
    profile_url: str = "https://truthsocial.com/@realDonaldTrump"

    # ── Scheduler ─────────────────────────────────────────────────────────────
    fetch_interval_seconds: int = Field(3000, env="FETCH_INTERVAL_SECONDS")
    batch_size: int = Field(50, env="BATCH_SIZE")

    # ── LLM Models ────────────────────────────────────────────────────────────
    sonnet_model: str = "claude-sonnet-4-6"
    opus_model: str = "claude-opus-4-6"

    # ── Embedding Model (local, free) ─────────────────────────────────────────
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ── Browser Session ───────────────────────────────────────────────────────
    session_max_age_seconds: int = 1800

    # ── Proxy cooldown after failure ──────────────────────────────────────────
    proxy_cooldown_seconds: int = Field(300, env="PROXY_COOLDOWN_SECONDS")

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field("INFO", env="LOG_LEVEL")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",  # ignore unknown env vars instead of crashing
    }


    @field_validator("proxies")
    @classmethod
    def validate_proxies(cls, v: str) -> str:
        entries = [e.strip() for e in v.split(",") if e.strip()]
        if not entries:
            raise ValueError("PROXIES must contain at least one proxy")
        for entry in entries:
            if len(entry.split(":", 3)) != 4:
                raise ValueError(
                    f"Invalid proxy format: '{entry}'. "
                    "Expected: server:port:username:password"
                )
        return v

    def get_proxy_list(self) -> list[ProxyConfig]:
        proxies = []
        for entry in self.proxies.split(","):
            entry = entry.strip()
            if not entry:
                continue
            host, port, username, password = entry.split(":", 3)
            proxies.append(ProxyConfig(
                server=f"{host}:{port}",
                username=username,
                password=password,
            ))
        return proxies


settings = Settings()