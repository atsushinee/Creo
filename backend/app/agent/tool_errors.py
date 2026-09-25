"""Middleware that isolates tool failures.

langchain 1.x's ToolNode re-raises unexpected tool exceptions, which would
abort the whole agent run. This middleware catches them and feeds the model a
`status="error"` ToolMessage instead, so the run continues and the UI renders
the tool card in its error state (MVP Case 3 / protocol `tool_result.isError`).
"""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware
from langchain_core.messages import ToolMessage
from langgraph.prebuilt.tool_node import ToolCallRequest


class ToolErrorMiddleware(AgentMiddleware):
    def wrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Any],
    ) -> Any:
        try:
            return handler(request)
        except Exception as exc:  # noqa: BLE001 — any tool failure becomes an error ToolMessage
            return self._error_message(request, exc)

    async def awrap_tool_call(
        self,
        request: ToolCallRequest,
        handler: Callable[[ToolCallRequest], Awaitable[Any]],
    ) -> Any:
        try:
            return await handler(request)
        except Exception as exc:  # noqa: BLE001
            return self._error_message(request, exc)

    @staticmethod
    def _error_message(request: ToolCallRequest, exc: Exception) -> ToolMessage:
        return ToolMessage(
            content=f"{type(exc).__name__}: {exc}",
            tool_call_id=str(request.tool_call.get("id") or ""),
            status="error",
        )
