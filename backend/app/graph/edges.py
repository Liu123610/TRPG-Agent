"""Conditional routes and edge rules."""

from langchain_core.messages import AIMessage

from app.graph.constants import ASSISTANT_NODE, END_NODE, ROUTER_NODE, TOOL_NODE, SUMMARIZE_NODE
from app.graph.state import GraphState


def route_from_router(state: GraphState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return END_NODE
    return ASSISTANT_NODE


def route_from_assistant(state: GraphState) -> str:
    messages = state.get("messages", [])
    if not messages:
        return END_NODE

    last_message = messages[-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return TOOL_NODE

    # [修改]：如果本轮后确认无需执行工具指令，检查上下文，判断是否由于消息过多需触发截断与大纲总结。
    # 放大触发阈值。TRPG 需要保留相对充沛的短期精细记忆。
    # 阈值设定为 > 40 条，即大约允许滑动窗口在 20~40 条之间移动。
    if len(messages) > 40:
        return SUMMARIZE_NODE
        
    return END_NODE


def route_from_tool(state: GraphState) -> str:
    return ASSISTANT_NODE


ROUTE_OPTIONS = {
    ASSISTANT_NODE: ASSISTANT_NODE,
    TOOL_NODE: TOOL_NODE,
    END_NODE: END_NODE,
}


ROUTER_NODE_NAME = ROUTER_NODE
