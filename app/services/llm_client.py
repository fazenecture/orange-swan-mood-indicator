from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """
    Unified LLM client with automatic Claude → OpenAI fallback.

    Claude is always tried first. On any failure — downtime, rate limit,
    timeout — OpenAI is used as fallback if configured.

    Mode mapping:
        sonnet → claude-sonnet / gpt-4o-mini  (cheap, fast)
        opus   → claude-opus  / gpt-4o        (powerful, expensive)
    """

    def __init__(self) -> None:
        self._claude_sonnet = ChatAnthropic(
            model=settings.sonnet_model,
            temperature=0.1,
            max_tokens=1000,
            api_key=settings.anthropic_api_key,
        )
        self._claude_opus = ChatAnthropic(
            model=settings.opus_model,
            temperature=0.2,
            max_tokens=2000,
            api_key=settings.anthropic_api_key,
        )
        self._openai_sonnet = (
            ChatOpenAI(
                model=settings.openai_sonnet_equivalent,
                temperature=0.1,
                max_tokens=1000,
                api_key=settings.openai_api_key,
            )
            if settings.openai_api_key
            else None
        )
        self._openai_opus = (
            ChatOpenAI(
                model=settings.openai_opus_equivalent,
                temperature=0.2,
                max_tokens=2000,
                api_key=settings.openai_api_key,
            )
            if settings.openai_api_key
            else None
        )

    def get_model(self, mode: str = "sonnet") -> BaseChatModel:
        """
        Returns the appropriate model with fallback.
        Always returns a LangChain BaseChatModel so callers
        don't need to know which provider is being used.
        """
        claude = self._claude_opus if mode == "opus" else self._claude_sonnet
        openai = self._openai_opus if mode == "opus" else self._openai_sonnet

        if openai is None:
            return claude

        # Wrap Claude with OpenAI fallback using LangChain's built-in
        return claude.with_fallbacks(
            [openai],
            exceptions_to_handle=(Exception,),
        )