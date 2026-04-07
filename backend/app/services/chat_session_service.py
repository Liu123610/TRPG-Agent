"""Chat session orchestration service for graph execution and persistence."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from app.config.settings import settings
from app.graph.builder import build_graph
from app.memory.checkpointer import get_checkpointer


class ChatSessionService:
    """Coordinates graph invocation with official thread-based checkpointing."""

    def __init__(self, graph: Any) -> None:
        self._graph = graph

    def process_turn(
        self,
        message: Optional[str] = None,
        session_id: Optional[str] = None,
        resume_action: Optional[str] = None,
    ) -> dict[str, Any]:
        current_session_id = session_id or str(uuid4())
        config = {"configurable": {"thread_id": current_session_id}}

        # Record the message count before this turn to compute delta reply.
        num_msgs_before = self._get_message_count(config)

        if resume_action:
            self._graph.invoke(Command(resume=resume_action), config=config)
        elif message:
            self._graph.invoke({"messages": [HumanMessage(content=message)]}, config=config)
        else:
            raise ValueError("Must provide either message or resume_action.")

        state = self._graph.get_state(config)

        return {
            "reply": self._extract_new_reply(state, num_msgs_before),
            "plan": None,
            "session_id": current_session_id,
            "pending_action": self._get_pending_action(state),
        }

    def _get_message_count(self, config: dict) -> int:
        """Return historical message count as baseline for delta extraction."""
        try:
            state = self._graph.get_state(config)
            return len(state.values.get("messages", [])) if state and hasattr(state, "values") else 0
        except Exception:
            return 0

    def _get_pending_action(self, state: Any) -> Optional[dict]:
        """Extract pending interrupt action from graph state."""
        if state.tasks and state.tasks[0].interrupts:
            return state.tasks[0].interrupts[0].value
        return None

    def _extract_new_reply(self, state: Any, num_msgs_before: int) -> str:
        """Extract plain-text AI reply generated during this turn."""
        all_messages = state.values.get("messages", [])
        new_messages = all_messages[num_msgs_before:]

        reply_parts: list[str] = []
        for msg in new_messages:
            if isinstance(msg, AIMessage) and msg.content:
                if isinstance(msg.content, str):
                    reply_parts.append(msg.content)
                elif isinstance(msg.content, list):
                    for part in msg.content:
                        if isinstance(part, str):
                            reply_parts.append(part)
                        elif isinstance(part, dict) and "text" in part:
                            reply_parts.append(part["text"])

        return "\n\n".join(reply_parts).strip()


@lru_cache(maxsize=1)
def get_chat_session_service() -> ChatSessionService:
    graph = build_graph(checkpointer=get_checkpointer(settings.memory_db_path))
    return ChatSessionService(graph=graph)
