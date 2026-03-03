from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.analysis.prompts.system_prompts import TRUMP_ANALYST_SYSTEM
from app.analysis.prompts.user_prompts import UserPromptBuilder
from app.services.llm_client import LLMClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

_MIN_POSTS_FOR_OPUS = 5


class MoodSynthesizer:
    """
    Produces the final mood assessment.

    Model selection per cycle:
        Opus   — high signal (shift detected, high intensity, burst posting)
        Sonnet — quiet cycles (stable mood, low intensity, few posts)

    Falls back to OpenAI automatically if Claude is down.
    Cuts synthesis cost ~60% on quiet days.
    """

    def __init__(self) -> None:
        self._llm_client = LLMClient()
        self._prompt_builder = UserPromptBuilder()
        # Build both chains upfront — swapped per cycle based on signal
        self._sonnet_chain = self._build_chain(mode="sonnet")
        self._opus_chain = self._build_chain(mode="opus")

    async def synthesize(
        self,
        state: dict,
        new_batch_summary: dict,
        new_posts: list[dict],
        rag_context: list[str] | None = None,
        world_context: str | None = None,
    ) -> dict:
        mode = self._pick_model(state, new_batch_summary, new_posts)

        # Sonnet gets batch summary only — raw posts omitted to save tokens
        # Opus gets full raw posts for deeper reasoning
        posts_for_prompt = new_posts if mode == "opus" else []

        prompt = self._prompt_builder.build_mood_synthesis_prompt(
            state,
            new_batch_summary,
            posts_for_prompt,
            rag_context,
            world_context=world_context,
        )

        logger.debug("Running mood synthesis via %s...", mode.upper())

        chain = self._opus_chain if mode == "opus" else self._sonnet_chain
        result = await chain.ainvoke({"user_prompt": prompt})

        logger.info(
            "Mood: %s | Intensity: %s | Shift: %s | Model: %s",
            result.get("current_mood"),
            result.get("intensity"),
            result.get("shift_detected"),
            mode.upper(),
        )
        return result

    # ── private ───────────────────────────────────────────────────────────────

    def _build_chain(self, mode: str):
        model = self._llm_client.get_model(mode=mode)
        return (
            ChatPromptTemplate.from_messages([
                ("system", TRUMP_ANALYST_SYSTEM),
                ("human", "{user_prompt}"),
            ])
            | model
            | JsonOutputParser()
        )

    def _pick_model(
        self,
        state: dict,
        batch_summary: dict,
        new_posts: list[dict],
    ) -> str:
        """
        Use Opus only when the cycle is genuinely high signal.
        Everything else uses Sonnet.
        """
        intensity = batch_summary.get("intensity", "low")
        trajectory = batch_summary.get("trajectory", "stable")
        post_count = len(new_posts)
        current_mood = state.get("current_mood", {}).get("label", "UNKNOWN")
        new_mood = batch_summary.get("dominant_mood", "")
        current_intensity = state.get("current_mood", {}).get("intensity", "low")

        reasons = []

        if intensity in ("high", "frenetic"):
            reasons.append(f"intensity={intensity}")

        if trajectory == "escalating":
            reasons.append("trajectory=escalating")

        if post_count > 15:
            reasons.append(f"post_count={post_count}")

        if new_mood and new_mood != current_mood:
            reasons.append(f"mood_shift={current_mood}→{new_mood}")

        if current_intensity == "frenetic":
            reasons.append("current=frenetic")

        if post_count < _MIN_POSTS_FOR_OPUS:
            logger.debug(
                "Using Sonnet — only %d posts, not enough signal", post_count
            )
            return "sonnet"

        if reasons:
            logger.info("Using Opus — %s", ", ".join(reasons))
            return "opus"

        logger.debug("Using Sonnet — low signal cycle")
        return "sonnet"