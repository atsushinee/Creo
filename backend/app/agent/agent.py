"""DeepAgents graph builder.

This module (together with runtime.py's consumption of its stream) is the ONLY
place in the codebase that imports deepagents / langchain agent internals.
Everything downstream speaks the Creo Agent Event Protocol (ADR-0002).
"""

from collections.abc import Callable
from typing import Any

from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver

from app.agent.model import create_model
from app.agent.tool_errors import ToolErrorMiddleware
from app.tools.demo_tools import DEMO_TOOLS


def build_agent(
    model: Any,
    instructions: str,
    checkpointer: MemorySaver | None = None,
    tools: list | None = None,
) -> Any:
    """Create the DeepAgents graph: system prompt + registered tools + memory.

    The checkpointer gives per-thread conversation memory (thread_id =
    session_id). DeepAgents API note (verified against 0.7.18): the system
    prompt parameter is `system_prompt`, not `instructions`. `tools` carries
    extra tools injected at composition time (e.g. the knowledge base
    retrieval tool, ADR-0004) and is merged after the built-in demo tools.
    """
    return create_deep_agent(
        model=model,
        tools=[*DEMO_TOOLS, *(tools or [])],
        system_prompt=instructions,
        checkpointer=checkpointer,
        middleware=[ToolErrorMiddleware()],
    )


def make_agent_builder(
    model_provider: str,
    model_name: str,
    instructions: str,
    model_api_key: str = "",
    model_base_url: str = "",
    extra_tools: list | None = None,
) -> Callable[[], Any]:
    """Return a lazily-invoked agent builder sharing one in-process checkpointer.

    Lazy on purpose: building the model may fail (e.g. missing provider API
    key) and must surface as an Agent `error` event on the first chat request,
    not as a server startup crash.
    """
    checkpointer = MemorySaver()

    def build() -> Any:
        model = create_model(
            provider=model_provider,
            name=model_name,
            api_key=model_api_key or None,
            base_url=model_base_url or None,
        )
        return build_agent(
            model=model,
            instructions=instructions,
            checkpointer=checkpointer,
            tools=extra_tools,
        )

    return build
