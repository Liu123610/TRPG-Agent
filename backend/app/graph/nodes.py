"""Graph node function implementations."""

import json
from functools import lru_cache

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage, RemoveMessage

from app.graph.state import GraphState
from app.services.llm_service import LLMService
from app.services.tool_service import get_tools

ASSISTANT_SYSTEM_PROMPT = (
    "你是一个专业的 TRPG 游戏核心主持人（DM/GM）。"
    "你的职责是推动剧情发展、回应玩家的探索与交互。"
    "在需要判定、对抗、查询角色属性等处理外部客观事实时，请务必使用工具（Tools）；如果玩家只是闲聊或剧情对话，请直接回复。"
)


@lru_cache(maxsize=1)
def _get_llm_service() -> LLMService:
    """使用 lru_cache 实现单例级别，获取大模型服务"""
    return LLMService()


def router_node(state: GraphState) -> GraphState:
    return {**state}


def assistant_node(state: GraphState) -> dict:
    messages = state.get("messages", [])
    
    # 动态组装附加了上下文的 System Prompt
    system_prompt = ASSISTANT_SYSTEM_PROMPT

    # 注入历史归纳大纲，保持大模型宏观长时记忆
    if summary := state.get("conversation_summary"):
        system_prompt += f"\n\n[前情提要（必须铭记的游戏大纲）]\n{summary}"

    if player := state.get("player"):
        player_context = json.dumps(player, ensure_ascii=False, indent=2)
        system_prompt += f"\n\n[当前玩家状态]\n{player_context}"
    else:
        system_prompt += "\n\n[当前玩家状态]\n玩家尚未加载或创建角色卡。"

    response = _get_llm_service().invoke_with_tools(
        messages=messages,
        tools=get_tools(),
        system_prompt=system_prompt,
    )

    output = response.content if isinstance(response.content, str) and not response.tool_calls else ""
    return {
        "messages": [response],
        "output": output,
    }


def summarize_conversation_node(state: GraphState) -> dict:
    """清理冗长对话记录：归纳极其老旧的消息，并发送指令将其丢弃卸载，释放窗口 token"""
    messages = state.get("messages", [])
    
    # 我们期望在截断时，至少在本地视窗中安全地留下最新的对局。此处放大为 20 条记录。
    keep_count = 20
    
    if len(messages) <= keep_count:
        return {}

    # 从右往左追溯：防范拦腰斩断 ToolMessage 导致 API 校验报 400 Bad Request 错误！
    while keep_count < len(messages):
        first_kept_msg = messages[-keep_count]
        if isinstance(first_kept_msg, ToolMessage):
            # 将指针向左扩大 1 格，强行将它的父级发起者（含 tool_calls 的 AIMessage）纳入保留区。
            keep_count += 1
            continue
        break
        
    msgs_to_summarize = messages[:-keep_count]
    if not msgs_to_summarize:
        return {}

    # 将该段早期的历史聊天交给 LLM 获取压缩大纲
    current_summary = state.get("conversation_summary", "")
    summary_prompt = (
        "这是一段 TRPG 游戏过往的部分对话。请将其客观浓缩，提炼出关键行为、物资增减及主干剧情。\n"
        "保持精简，拒绝任何修饰语。这段记录将被遗忘，此总结将作为继承给未来的核心大纲：\n\n"
    )
    
    if current_summary:
        summary_prompt = f"之前累积的大纲如下：\n{current_summary}\n\n" + summary_prompt
        
    summary_prompt += "【新发生的即将被遗弃的历史对话】\n"
    for m in msgs_to_summarize:
        role = m.__class__.__name__.replace("Message", "")
        # 处理 list 等复合 content
        content = m.content
        if isinstance(content, list):
            content = " ".join(str(x) for x in content if isinstance(x, str) or (isinstance(x, dict) and x.get("text")))
        summary_prompt += f"[{role}]: {content}\n"
        
    response = _get_llm_service().invoke_with_tools(
        messages=[HumanMessage(content=summary_prompt)],
        tools=[],  # 纯提炼节点，关闭 tool 防发散
        system_prompt="你是一个极度严谨的记忆整理员。请生成一段客观、简短且剥离所有情感修饰的核心内容摘要，帮助系统长效保存历史进程。",
    )
    
    new_summary = str(response.content).strip()
    
    # 利用原生的 RemoveMessage 发送销毁指令给 StateGraph Checkpointer。必须要确保 m.id 存在才能销毁（langchain > 0.2 原生全带 ID）
    delete_msgs = [RemoveMessage(id=m.id) for m in msgs_to_summarize if getattr(m, "id", None)]
    
    return {
        "conversation_summary": new_summary,
        "messages": delete_msgs
    }
