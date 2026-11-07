"""Tom the cat agent (LangGraph + Groq)."""
from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver

from characters import generate_tom_prompt
from band import Agent, configure_logging
from band.adapters import LangGraphAdapter, LangGraphAdapterConfig

configure_logging(logging.INFO)
logger = logging.getLogger(__name__)


def groq_llm() -> ChatOpenAI:
    """Groq uses the OpenAI-compatible Chat Completions API."""
    return ChatOpenAI(
        model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
        api_key=os.getenv("GROQ_API_KEY"),
        base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
        temperature=0.6,
    )


async def main() -> None:
    load_dotenv(override=True)
    adapter = LangGraphAdapter(
        LangGraphAdapterConfig(custom_section=generate_tom_prompt("Tom")),
        llm=groq_llm(),
        checkpointer=InMemorySaver(),
    )
    logger.info("Tom is ready to audit WHATIF business scenarios.")
    async with Agent.from_config("tom_agent", adapter=adapter) as agent:
        await agent.run_forever()


if __name__ == "__main__":
    asyncio.run(main())

