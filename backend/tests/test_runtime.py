"""Integration tests for AgentRuntime: real DeepAgents graph + scripted model.

These tests validate the runtime event converter against the actual installed
deepagents/stream behavior without any network access.
"""

from langgraph.checkpoint.memory import MemorySaver

from app.agent.agent import build_agent
from app.agent.runtime import AgentRuntime
from app.models.events import RunFinished, RunStarted
from tests.fakes import ScriptedChatModel, text_chunks, tool_call_chunk

SESSION = "runtime-test-session"


def make_runtime(script) -> AgentRuntime:
    model = ScriptedChatModel(script=script)
    return AgentRuntime(
        agent_builder=lambda: build_agent(
            model=model, instructions="test prompt", checkpointer=MemorySaver()
        )
    )


async def collect(runtime: AgentRuntime, message: str) -> list:
    return [event async for event in runtime.stream_events(SESSION, message)]


async def test_full_tool_call_flow() -> None:
    runtime = make_runtime(
        [
            text_chunks("Let me compute. ")
            + [tool_call_chunk("calculator", '{"expression": "123*456"}', "call_1")],
            text_chunks("The result is 56088."),
        ]
    )
    events = await collect(runtime, "计算 123 * 456")
    types = [event.type for event in events]

    assert types[0] == "run_started"
    assert types[-1] == "run_finished"
    assert "error" not in types

    tool_starts = [e for e in events if e.type == "tool_start"]
    assert len(tool_starts) == 1
    assert tool_starts[0].toolName == "calculator"
    assert tool_starts[0].args == {"expression": "123*456"}

    tool_results = [e for e in events if e.type == "tool_result"]
    assert len(tool_results) == 1
    assert tool_results[0].toolCallId == tool_starts[0].toolCallId
    assert tool_results[0].result == "56088"
    assert tool_results[0].isError is False

    # Protocol ordering: message text closes before its tool call starts.
    text_before_tool = "".join(
        e.content for e in events if e.type == "message_delta"
    )
    assert "Let me compute." in text_before_tool
    assert "56088" in text_before_tool

    deltas_idx = types.index("message_delta")
    tool_start_idx = types.index("tool_start")
    assert deltas_idx < tool_start_idx

    # run_started first, run_finished last.
    assert isinstance(events[0], RunStarted)
    assert isinstance(events[-1], RunFinished)

    # The session trace mirrors the structural events for the trace viewer.
    trace = runtime.get_session_trace(SESSION)
    trace_types = [entry["type"] for entry in trace]
    assert trace_types[0] == "user_message"
    assert "计算 123 * 456" in trace[0]["message"]
    assert "tool_start" in trace_types and "tool_result" in trace_types
    tool_entry = next(entry for entry in trace if entry["type"] == "tool_start")
    assert tool_entry["toolName"] == "calculator"
    assert tool_entry["args"] == {"expression": "123*456"}
    result_entry = next(entry for entry in trace if entry["type"] == "tool_result")
    assert result_entry["result"] == "56088"
    message_end = next(entry for entry in trace if entry["type"] == "message_end")
    assert message_end["durationMs"] >= 0 and message_end["chars"] > 0
    assert trace_types[-1] == "run_finished"


async def test_tool_error_is_reported_not_raised() -> None:
    runtime = make_runtime(
        [
            [tool_call_chunk("calculator", '{"expression": "1/0"}', "call_err")],
            text_chunks("The calculation failed, sorry."),
        ]
    )
    events = await collect(runtime, "break it")
    types = [event.type for event in events]

    assert "error" not in types  # tool failure ≠ run failure
    results = [e for e in events if e.type == "tool_result"]
    assert len(results) == 1
    assert results[0].isError is True
    assert results[0].result  # error text is surfaced
    assert types[-1] == "run_finished"


async def test_unconfigured_agent_yields_error_event() -> None:
    def broken_builder() -> None:
        msg = "no API key configured"
        raise RuntimeError(msg)

    runtime = AgentRuntime(agent_builder=broken_builder)
    events = await collect(runtime, "hello")
    types = [event.type for event in events]

    assert types == ["run_started", "error", "run_finished"]
    assert "no API key configured" in events[1].message


async def test_history_reconstruction() -> None:
    runtime = make_runtime(
        [
            [tool_call_chunk("calculator", '{"expression": "2+2"}', "call_h")],
            text_chunks("It is 4."),
        ]
    )
    await collect(runtime, "what is 2+2")

    history = await runtime.get_history(SESSION)
    roles = [entry.role for entry in history]
    assert roles == ["user", "assistant", "assistant"]

    user, assistant_with_tool, assistant_final = history
    assert user.content == "what is 2+2"
    assert assistant_with_tool.content == ""
    assert len(assistant_with_tool.tools) == 1
    record = assistant_with_tool.tools[0]
    assert record.toolName == "calculator"
    assert record.args == {"expression": "2+2"}
    assert record.result == "4"
    assert record.isError is False
    assert assistant_final.content == "It is 4."
    assert assistant_final.tools == []
