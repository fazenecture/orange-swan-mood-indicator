from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableSequence

from app.analysis.prompts.system_prompts import TRUMP_ANALYST_SYSTEM
from app.analysis.prompts.user_prompts import UserPromptBuilder
from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class MoodSynthesizer:
    """
    Produces the final mood assessment using Opus (smarter, deeper reasoning).
    Called ONCE per fetch cycle — receives compressed batch summaries, not raw posts.
    This keeps token usage and cost minimal.
    """

    def __init__(self) -> None:
        self._chain: RunnableSequence | None = None
        self._prompt_builder = UserPromptBuilder()

    async def synthesize(
        self,
        state: dict,
        new_batch_summary: dict,
        new_posts: list[dict],
        rag_context: list[str] | None = None,
    ) -> dict:
        prompt = self._prompt_builder.build_mood_synthesis_prompt(
            state, new_batch_summary, new_posts, rag_context
        )
        logger.debug("Running mood synthesis...")
        result = await self._get_chain().ainvoke({"user_prompt": prompt})

        logger.info(
            "Mood: %s | Intensity: %s | Shift: %s",
            result.get("current_mood"),
            result.get("intensity"),
            result.get("shift_detected"),
        )
        return result

    # ── private ───────────────────────────────────────────────────────────────

    def _get_chain(self) -> RunnableSequence:
        if self._chain is None:
            model = ChatAnthropic(
                model=settings.opus_model,
                temperature=0.2,
                max_tokens=2000,
                api_key=settings.anthropic_api_key
            )
            self._chain = RunnableSequence(
                ChatPromptTemplate.from_messages([
                    ("system", TRUMP_ANALYST_SYSTEM),
                    ("human", "{user_prompt}"),
                ]),
                model,
                JsonOutputParser(),
            )
        return self._chain
