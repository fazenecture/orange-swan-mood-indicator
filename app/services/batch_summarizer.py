import asyncio

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from app.analysis.prompts.system_prompts import BATCH_SUMMARIZER_SYSTEM
from app.analysis.prompts.user_prompts import UserPromptBuilder
from app.services.llm_client import LLMClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


class BatchSummarizer:
    """
    Summarizes batches of posts using Sonnet (faster, cheaper).
    Multiple batches run concurrently — limited to 5 parallel calls.
    Always uses sonnet mode — batch summarization never needs Opus.
    Falls back to OpenAI automatically if Claude is down.
    """

    def __init__(self) -> None:
        self._llm_client = LLMClient()
        self._prompt_builder = UserPromptBuilder()
        self._chain = self._build_chain()

    async def summarize_batch(
        self,
        posts: list[dict],
        batch_index: int = 0,
        total_batches: int = 1,
        world_context: str = "",
    ) -> dict:
        prompt = self._prompt_builder.build_batch_summary_prompt(
            posts, batch_index, total_batches, world_context
        )
        logger.debug("Summarizing batch %d/%d", batch_index + 1, total_batches)
        return await self._chain.ainvoke({"user_prompt": prompt})

    async def summarize_all(
        self,
        posts: list[dict],
        batch_size: int = 50,
        world_context: str = "",
    ) -> list[dict]:
        """Bulk processing — runs batches concurrently with rate limiting."""
        batches = self._chunk(posts, batch_size)
        total = len(batches)
        results = []

        for i in range(0, total, 5):
            group = batches[i: i + 5]
            group_results = await asyncio.gather(*[
                self.summarize_batch(batch, i + j, total, world_context)
                for j, batch in enumerate(group)
            ])
            results.extend(group_results)
            if i + 5 < total:
                await asyncio.sleep(0.5)

        return results

    # ── private ───────────────────────────────────────────────────────────────

    def _build_chain(self):
        model = self._llm_client.get_model(mode="sonnet")
        return (
            ChatPromptTemplate.from_messages([
                ("system", BATCH_SUMMARIZER_SYSTEM),
                ("human", "{user_prompt}"),
            ])
            | model
            | JsonOutputParser()
        )

    def _chunk(self, lst: list, size: int) -> list[list]:
        return [lst[i: i + size] for i in range(0, len(lst), size)]