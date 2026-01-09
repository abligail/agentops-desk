from __future__ import annotations

import logging
import os
from typing import Any, Optional

from agents import Agent, Runner, ModelSettings, OpenAIChatCompletionsModel
from agents.mcp import MCPServerStreamableHttp
from openai import AsyncOpenAI

from . import langfuse_client

FOOD_MCP_URL = os.getenv("FOOD_MCP_URL", "http://127.0.0.1:8007/mcp")

DEFAULT_SYSTEM_PROMPT = """
You are the Food Service Agent for an airline.
Use MCP tools to answer questions and manage meal requests:
- If account_number is provided, call fetch_customer_profile first.
- Use check_menu_options to list meal options.
- Use record_meal_preference, then confirm_meal_selection after the customer agrees.
Always pass conversation_id/account_number/confirmation_number/flight_number/seat_number if available.
""".strip()


def _build_eval_model(model_name: Optional[str]) -> OpenAIChatCompletionsModel:
    use_openai = os.getenv("USE_OPENAI_MODEL", "true").lower() == "true"
    if use_openai:
        base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        api_key = os.getenv("OPENAI_API_KEY", "")
        default_model = os.getenv("OPENAI_MODEL_NAME_MINI", "gpt-4.1-mini")
    else:
        base_url = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        api_key = os.getenv("QWEN_API_KEY", "")
        default_model = os.getenv("QWEN_MODEL_NAME_MINI", "qwen3-next-80b-a3b-instruct")

    resolved_model = model_name or default_model
    if not api_key:
        raise RuntimeError("Missing API key for evaluation model")

    client = AsyncOpenAI(base_url=base_url, api_key=api_key)
    logging.info("Eval model: %s (base_url=%s)", resolved_model, base_url)
    return OpenAIChatCompletionsModel(model=resolved_model, openai_client=client)


class InstrumentedMCPServer(MCPServerStreamableHttp):
    def __init__(
        self,
        *args,
        tool_call_history: list[dict[str, Any]],
        trajectory: Optional[list[str]] = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self._tool_call_history = tool_call_history
        self._trajectory = trajectory if trajectory is not None else []

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None):
        args = arguments or {}
        logging.info("Tool call: %s %s", tool_name, args)
        self._trajectory.append(tool_name)
        record = {"tool_name": tool_name, "args": args}
        self._tool_call_history.append(record)
        out = await super().call_tool(tool_name, arguments)
        record["ok"] = not getattr(out, "isError", False)
        return out


def _build_prompt(payload: dict[str, Any]) -> str:
    question = payload.get("question", "")
    context_lines = []
    for key in (
        "account_number",
        "confirmation_number",
        "flight_number",
        "seat_number",
        "conversation_id",
        "dietary_notes",
        "special_requests",
    ):
        value = payload.get(key)
        if value:
            context_lines.append(f"{key}: {value}")
    context = "\n".join(context_lines) if context_lines else "none"
    return f"Customer question: {question}\n\nKnown context:\n{context}"


async def run_agent(
    item,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    model: Optional[str] = None,
):
    langfuse_client.update_current_trace(input=item.input)
    logging.info("Food MCP URL: %s", FOOD_MCP_URL)

    tool_call_history: list[dict[str, Any]] = []
    trajectory: list[str] = []
    eval_model = _build_eval_model(model)

    async with InstrumentedMCPServer(
        name="food-service-mcp",
        params={"url": FOOD_MCP_URL, "timeout": 30},
        client_session_timeout_seconds=30,
        cache_tools_list=True,
        max_retry_attempts=1,
        tool_call_history=tool_call_history,
        trajectory=trajectory,
    ) as server:
        agent = Agent(
            name="FoodServiceEvalAgent",
            instructions=system_prompt,
            model=eval_model,
            mcp_servers=[server],
            model_settings=ModelSettings(tool_choice="required"),
        )
        prompt = _build_prompt(item.input)
        result = await Runner.run(agent, prompt)

    langfuse_client.update_current_trace(
        output=result.final_output,
        metadata={"trajectory": trajectory},
    )
    langfuse_client.flush()

    return {
        "trajectory": trajectory,
        "final_response": result.final_output,
        "tool_call_history": tool_call_history,
    }
