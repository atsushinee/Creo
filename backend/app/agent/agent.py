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
) -> Any:
    """Create the DeepAgents graph: system prompt + registered tools + memory.

    The checkpointer gives per-thread conversation memory (thread_id =
    session_id). DeepAgents API note (verified against 0.7.18): the system
    prompt parameter is `system_prompt`, not `instructions`.
    """
    return create_deep_agent(
        model=model,
        tools=list(DEMO_TOOLS),
        system_prompt=instructions,
        checkpointer=checkpointer,
        middleware=[ToolErrorMiddleware()],
    )


def make_agent_builder(model_spec: str, instructions: str) -> Callable[[], Any]:
    """Return a lazily-invoked agent builder sharing one in-process checkpointer.

    Lazy on purpose: building the model may fail (e.g. missing provider API
    key) and must surface as an Agent `error` event on the first chat request,
    not as a server startup crash.
    """
    checkpointer = MemorySaver()

    def build() -> Any:
        model = create_model(model_spec)
        return build_agent(model=model, instructions=instructions, checkpointer=checkpointer)

    return build
