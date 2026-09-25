/**
 * Creo Agent Event Protocol — frontend mirror of backend/app/models/events.py.
 * Keep both files in sync; see docs/decisions/0002-agent-event-protocol.md.
 */

export interface RunStartedEvent {
  type: "run_started";
  runId: string;
}

export interface MessageStartEvent {
  type: "message_start";
  messageId: string;
}

export interface MessageDeltaEvent {
  type: "message_delta";
  messageId: string;
  content: string;
}

export interface MessageEndEvent {
  type: "message_end";
  messageId: string;
}

export interface ToolStartEvent {
  type: "tool_start";
  toolCallId: string;
  toolName: string;
  args: unknown;
}

export interface ToolResultEvent {
  type: "tool_result";
  toolCallId: string;
  result: unknown;
  isError?: boolean;
}

export interface ErrorEvent {
  type: "error";
  message: string;
}

export interface RunFinishedEvent {
  type: "run_finished";
  runId: string;
}

export type AgentEvent =
  | RunStartedEvent
  | MessageStartEvent
  | MessageDeltaEvent
  | MessageEndEvent
  | ToolStartEvent
  | ToolResultEvent
  | ErrorEvent
  | RunFinishedEvent;

/* Reserved for future phases — do not emit yet (update ADR-0002 first):
   approval_required, state_update, artifact_created, artifact_updated,
   source_added, agent_status */

export type ToolStatus = "running" | "success" | "error";

export interface ToolInvocation {
  toolCallId: string;
  toolName: string;
  args?: unknown;
  result?: unknown;
  status: ToolStatus;
}

export type MessagePart =
  | { kind: "text"; text: string }
  | { kind: "tool"; tool: ToolInvocation };

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  parts: MessagePart[];
  status: "complete" | "streaming" | "error";
  createdAt: string;
}

export interface SessionInfo {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface HistoryToolRecord {
  toolCallId: string;
  toolName: string;
  args?: unknown;
  result?: unknown;
  isError?: boolean;
}

export interface HistoryMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  tools: HistoryToolRecord[];
}
