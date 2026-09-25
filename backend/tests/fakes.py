"""Test doubles: a scripted chat model that streams pre-written chunks.

Used to exercise the real DeepAgents graph and the runtime event converter
without any network access or API key.
"""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import PrivateAttr


class ScriptedChatModel(BaseChatModel):
    """Yields pre-scripted chunk sequences; one sequence per model invocation."""

    script: list[list[AIMessageChunk]]
    _turn: int = PrivateAttr(default=0)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":  # noqa: ARG002
        return self

    def _generate(  # type: ignore[override]
        self,
        messages: Any,
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        chunks = self.script[self._turn % len(self.script)]
        self._turn += 1
        final: AIMessageChunk | None = None
        for chunk in chunks:
            final = chunk if final is None else final + chunk
        assert final is not None, "scripted turns must not be empty"
        return ChatResult(generations=[ChatGeneration(message=final)])

    def _stream(  # type: ignore[override]
        self,
        messages: Any,
        stop: Any = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Any:
        chunks = self.script[self._turn % len(self.script)]
        self._turn += 1
        for chunk in chunks:
            if run_manager is not None:
                run_manager.on_llm_new_token(chunk.text(), chunk=chunk)
            yield ChatGenerationChunk(message=chunk)


def text_chunks(*pieces: str) -> list[AIMessageChunk]:
    return [AIMessageChunk(content=piece) for piece in pieces]


def tool_call_chunk(tool_name: str, args_json: str, call_id: str) -> AIMessageChunk:
    return AIMessageChunk(
        content="",
        tool_call_chunks=[
            {
                "name": tool_name,
                "args": args_json,
                "id": call_id,
                "index": 0,
                "type": "tool_call",
            }
        ],
    )
