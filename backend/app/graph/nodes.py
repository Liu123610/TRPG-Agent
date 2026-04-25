"""Graph node function implementations."""

import json
from copy import copy
from functools import lru_cache

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, RemoveMessage, ToolMessage

from app.graph.constants import COMBAT_AGENT_MODE, NARRATIVE_AGENT_MODE
from app.graph.state import GraphState
from app.services.llm_service import LLMService
from app.services.tool_service import get_tool_profile

ASSISTANT_SYSTEM_PROMPT = (
    "你是一个专业的 TRPG 游戏核心主持人（DM/GM）。"
    "你的职责是推动剧情发展、回应玩家的探索与交互。"
    "在需要判定、对抗、查询角色属性等处理外部客观事实时，请务必使用工具（Tools）；如果玩家只是闲聊或剧情对话，请直接回复。\n\n"

    "【行动准则】\n"
    "1. 工具优先：当你决定执行一个动作时（攻击、掷骰、生成怪物等），立即调用对应工具。"
    "绝对不要先输出「我将使用…」之类的预告文本再调用工具，这会造成冗余延迟。\n"
    "2. 回合意识：在调用 attack_action 之前，必须核对下方注入的战斗状态中的 current_actor_id 字段，"
    "确认当前行动者确实是你要操作的单位。不要盲目发起攻击。\n"
    "3. 武器真实性：攻击时只能使用战斗状态中该单位 attacks 列表里实际存在的武器名称，"
    "不要编造或猜测武器名。\n"
    "4. 战斗简洁模式：在战斗阶段（phase=combat），使用简洁的播报风格，1-2 句话概括工具返回的结果即可。"
    "不要使用表情符号，不要输出大段剧情描写。\n"
    "5. 怪物回合结算：当你看到 [系统:怪物行动] 或 [系统:怪物回合结算] 标记的消息时，"
    "简要向玩家转述关键战果（谁攻击了谁、造成多少伤害），然后询问玩家的行动。\n"
    "6. 工具结果权威性：当你调用任何战斗工具（attack_action, next_turn 等）后，"
    "工具返回的结果是唯一的事实来源。如果工具返回错误信息（如'不是你的回合'、'动作已用尽'），"
    "你必须如实向玩家转达该错误，绝对不能忽略错误而自行编造攻击效果。\n"
    "7. 禁止虚构战斗结果：在战斗阶段，你绝不可以在没有成功调用 attack_action 工具的情况下"
    "描述任何攻击命中、伤害或 HP 变化。所有战斗数值必须来自工具返回。\n"
    "8. 状态变更规范：所有涉及角色 HP、AC、能力值、状态效果等变化，必须通过 modify_character_state 工具执行，"
    "不要自行编造数值后果。\n"
    "9. 场景单位管理：spawn_monsters 生成的单位进入场景单位池。开战前你需要获取可用单位 ID 列表，"
    "并通过 start_combat 的 combatant_ids 参数指定参战者。未参战单位仍保留在场景中。\n"
    "10. 死亡单位：战斗结束后，死亡单位会归入死亡档案。若玩家希望搜刮尸体等，可描述剧情后使用 clear_dead_units 清理。\n"
    "11. 法术施放：使用 cast_spell 工具施放法术，系统自动处理法术位消耗、命中/豁免判定和伤害/治疗计算。"
    "施法前确认角色已知该法术且有足够法术位。反应法术（如护盾术）可在任意单位回合施放。\n"
    "12. 单位查询：使用 inspect_unit 查看任意单位完整属性（HP、AC、攻击列表、法术位等）。"
    "在需要了解目标详情时使用此工具，而非编造数据。\n"
    "13. 资源管理：法术位等资源通过 cast_spell 自动消耗。如需手动调整（如长休恢复法术位），"
    "使用 modify_character_state 的 resource_delta 或 set_resource 键。\n"
)

COMBAT_ASSISTANT_SYSTEM_PROMPT = (
    ASSISTANT_SYSTEM_PROMPT
    + "\n"
    + "【战斗代理补充准则】\n"
    + "1. 你负责战斗阶段所有单位的回合决策与简洁播报，不要展开长篇剧情描写。\n"
    + "2. 当上一条是工具或系统战报时，先吸收其中的命中、伤害、状态变化，再决定是否继续调用工具。\n"
    + "3. 当当前行动者是怪物或 NPC 时，你必须直接代表它完成合法回合，不要先向玩家提问。\n"
    + "4. 若当前行动者无法再执行有效动作，优先调用 next_turn，而不是停留在空泛描述。\n"
    + "5. 若战斗已经结束或 combat 为空，立即回到正常叙事口吻，不要继续以战斗代理自居。\n"
)


@lru_cache(maxsize=1)
def _get_llm_service() -> LLMService:
    """使用 lru_cache 实现单例级别，获取大模型服务"""
    return LLMService()


def router_node(state: GraphState) -> dict:
    # Do not return the entire state to avoid duplicate updates in stream_mode="updates"
    return {}


# 兼容旧入口，探索阶段仍沿用 assistant 节点名。
def assistant_node(state: GraphState) -> dict:
    return _invoke_assistant(state, mode=NARRATIVE_AGENT_MODE)


# 战斗阶段统一入口，玩家与怪物回合都走同一 combat assistant。
def combat_assistant_node(state: GraphState) -> dict:
    return _invoke_assistant(state, mode=COMBAT_AGENT_MODE)


def _invoke_assistant(state: GraphState, mode: str) -> dict:
    from app.utils.logger import logger

    model_input_messages = _build_model_input_messages(state, mode)
    hud_text = _build_hud_text(state)
    system_prompt = _build_system_prompt(state, mode)
    tools = get_tool_profile(mode)

    logger.info("=== [%s Assistant Invocation] ===", mode)
    logger.debug("HUD Info [injected into latest message]:\n%s", hud_text)
    logger.debug("--- [Projected Message Dialogue & Context History] ---")
    for i, msg in enumerate(model_input_messages):
        msg_type = msg.__class__.__name__
        content_text = _message_content_to_text(msg.content)
        content_preview = content_text[:200] + "..." if len(content_text) > 200 else content_text
        logger.debug("Msg %s [%s]: %s", i, msg_type, content_preview)

    response = _get_llm_service().invoke_with_tools(
        messages=model_input_messages,
        tools=tools,
        system_prompt=system_prompt,
        mode=mode,
    )

    if hasattr(response, "tool_calls") and response.tool_calls:
        logger.info("LLM Called Tools -> %s", response.tool_calls)
    else:
        info_resp = str(getattr(response, "content", ""))[:100]
        logger.info("LLM Responsed [Text] -> %s...", info_resp)

    output = response.content if isinstance(response.content, str) and not response.tool_calls else ""
    return {
        "messages": [response],
        "output": output,
    }


def _build_system_prompt(state: GraphState, mode: str) -> str:
    system_prompt = COMBAT_ASSISTANT_SYSTEM_PROMPT if mode == COMBAT_AGENT_MODE else ASSISTANT_SYSTEM_PROMPT

    if summary := state.get("conversation_summary"):
        system_prompt += f"\n\n[前情提要（必须铭记的游戏大纲）]\n{summary}"

    if mode == COMBAT_AGENT_MODE:
        combat_brief = _build_combat_brief(state)
        if combat_brief:
            system_prompt += f"\n\n[战斗简报]\n{combat_brief}"

        turn_directive = _build_combat_turn_directive(state)
        if turn_directive:
            system_prompt += f"\n\n[当前回合指令]\n{turn_directive}"

    return system_prompt


def _build_combat_brief(state: GraphState) -> str:
    combat_dict = _state_value_to_dict(state.get("combat"))
    if not combat_dict:
        return ""

    player_dict = _state_value_to_dict(state.get("player"))
    participants = dict(combat_dict.get("participants", {}))
    if player_dict and player_dict.get("id"):
        participants[player_dict["id"]] = player_dict

    current_id = combat_dict.get("current_actor_id", "")
    current_actor = participants.get(current_id, {})
    lines = [
        f"第 {combat_dict.get('round', '?')} 回合，当前行动者 {current_actor.get('name', current_id)} [ID:{current_id}]。",
        f"先攻顺序: {combat_dict.get('initiative_order', [])}",
    ]

    if scene_summary := state.get("scene_summary"):
        lines.append(f"当前局势/战斗 stakes: {scene_summary}")

    player_side: list[str] = []
    enemy_side: list[str] = []
    for uid, combatant in participants.items():
        status = (
            f"{combatant.get('name', uid)}[HP:{combatant.get('hp')}/{combatant.get('max_hp')}, "
            f"AC:{combatant.get('ac')}, conditions:{_format_conditions(combatant)}, "
            f"attacks:{_format_attacks(combatant)}]"
        )
        if combatant.get("side") == "player":
            player_side.append(status)
        else:
            enemy_side.append(status)

    if player_side:
        lines.append("玩家侧: " + "；".join(player_side))
    if enemy_side:
        lines.append("对立侧: " + "；".join(enemy_side))

    return "\n".join(lines)


def _build_combat_turn_directive(state: GraphState) -> str:
    """用共享状态显式说明当前回合由谁决策，避免在单线程里隐式切换职责。"""
    combat_dict = _state_value_to_dict(state.get("combat"))
    if not combat_dict:
        return ""

    player_dict = _state_value_to_dict(state.get("player"))
    current_id = combat_dict.get("current_actor_id", "")
    participants = dict(combat_dict.get("participants", {}))
    if player_dict and player_dict.get("id"):
        participants[player_dict["id"]] = player_dict

    current_actor = participants.get(current_id, {})
    current_name = current_actor.get("name", current_id)
    if current_actor.get("side") == "player":
        return (
            f"当前是玩家单位 {current_name} [ID:{current_id}] 的回合。"
            "根据玩家最新意图调用合适工具；若本回合已无合理动作，再调用 next_turn。"
        )

    return (
        f"当前是怪物/NPC {current_name} [ID:{current_id}] 的回合。"
        "你必须直接为其选择一个合法目标和攻击或法术并调用工具；"
        "若动作已用尽、被状态阻止，或已无存活敌人，则立即调用 next_turn。"
    )


def _build_hud_text(state: GraphState) -> str:
    sections: list[str] = []

    player_dict = _state_value_to_dict(state.get("player"))
    if player_dict:
        sections.append("[当前玩家状态]\n" + json.dumps(player_dict, ensure_ascii=False, indent=2))
    else:
        sections.append("[当前玩家状态]\n玩家尚未加载或创建角色卡。")

    combat_dict = _state_value_to_dict(state.get("combat"))
    if combat_dict:
        current_id = combat_dict.get("current_actor_id", "")
        participants = dict(combat_dict.get("participants", {}))
        if player_dict and player_dict.get("id"):
            participants[player_dict["id"]] = player_dict

        combat_lines = [
            f"第 {combat_dict.get('round', '?')} 回合 | 当前行动者: {current_id}",
            f"先攻顺序: {combat_dict.get('initiative_order', [])}",
        ]
        for uid, combatant in participants.items():
            attacks_desc = _format_attacks(combatant)
            marker = " ← 当前行动" if uid == current_id else ""
            combat_lines.append(
                f"  {combatant.get('name', uid)} [ID:{uid}] side={combatant.get('side')} "
                f"HP:{combatant.get('hp')}/{combatant.get('max_hp')} AC:{combatant.get('ac')} "
                f"conditions=[{_format_conditions(combatant)}] attacks=[{attacks_desc}]{marker}"
            )
        sections.append("[当前战斗状态]\n" + "\n".join(combat_lines))

    scene_units = state.get("scene_units")
    scene_data = _dump_mapping_state(scene_units)
    if scene_data:
        scene_lines = [
            f"  {uid}: {unit.get('name', uid)} (side={unit.get('side')}, HP:{unit.get('hp')}/{unit.get('max_hp')})"
            for uid, unit in scene_data.items()
        ]
        sections.append("[场景单位池（可用 start_combat 指定参战）]\n" + "\n".join(scene_lines))

    dead_units = state.get("dead_units")
    dead_data = _dump_mapping_state(dead_units)
    if dead_data:
        dead_lines = [f"  {uid}: {unit.get('name', uid)}" for uid, unit in dead_data.items()]
        sections.append("[死亡单位档案]\n" + "\n".join(dead_lines))

    return "\n\n=== 实时系统监控窗(HUD) ===\n" + "\n\n".join(sections) + "\n===========================\n"


def _dump_mapping_state(value) -> dict:
    if not value or not hasattr(value, "items"):
        return {}
    return {
        key: item.model_dump() if hasattr(item, "model_dump") else dict(item)
        for key, item in value.items()
    }


def _build_model_input_messages(state: GraphState, mode: str) -> list[BaseMessage]:
    source_messages = list(state.get("messages", []))
    trimmed_messages = _trim_model_messages(source_messages, mode)
    projected_messages: list[BaseMessage] = []

    for message in trimmed_messages:
        if isinstance(message, ToolMessage):
            projected_messages.append(_clone_message_with_content(message, _summarize_tool_message(message)))
            continue

        if isinstance(message, HumanMessage) and isinstance(message.content, str) and message.content.startswith("[系统:"):
            projected_messages.append(_clone_message_with_content(message, _summarize_system_message(message.content)))
            continue

        projected_messages.append(message)

    return _append_hud_to_latest_message(projected_messages, _build_hud_text(state))


def _trim_model_messages(messages: list[BaseMessage], mode: str) -> list[BaseMessage]:
    keep_count = 50 if mode == NARRATIVE_AGENT_MODE else 32
    if len(messages) <= keep_count:
        return list(messages)

    start_index = len(messages) - keep_count
    while start_index > 0 and isinstance(messages[start_index], ToolMessage):
        start_index -= 1

    return list(messages[start_index:])


def _append_hud_to_latest_message(messages: list[BaseMessage], hud_text: str) -> list[BaseMessage]:
    if not messages:
        return []

    projected_messages = list(messages)
    projected_messages[-1] = _clone_message_with_content(projected_messages[-1], _append_text_content(projected_messages[-1].content, hud_text))
    return projected_messages


def _clone_message_with_content(message: BaseMessage, content) -> BaseMessage:
    cloned_message = copy(message)
    cloned_message.content = content
    return cloned_message


def _append_text_content(content, extra_text: str):
    if isinstance(content, str):
        return content + extra_text
    if isinstance(content, list):
        appended_content = list(content)
        appended_content.append({"type": "text", "text": extra_text})
        return appended_content
    return f"{content}{extra_text}"


def _message_content_to_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _format_conditions(combatant: dict) -> str:
    conditions = combatant.get("conditions", []) or []
    if not conditions:
        return "无"
    return ", ".join(condition.get("name_cn") or condition.get("id", "?") for condition in conditions)


def _format_attacks(combatant: dict) -> str:
    attacks = combatant.get("attacks", []) or []
    if not attacks:
        return "无"
    return ", ".join(attack.get("name", "?") for attack in attacks)


def _summarize_tool_message(message: ToolMessage) -> str:
    tool_name = getattr(message, "name", "") or "tool"
    raw_text = _message_content_to_text(message.content).strip()

    if tool_name == "request_dice_roll":
        try:
            roll_data = json.loads(raw_text)
        except json.JSONDecodeError:
            roll_data = None
        if isinstance(roll_data, dict):
            raw_roll = roll_data.get("raw_roll", "?")
            final_total = roll_data.get("final_total", raw_roll)
            return f"[工具:{tool_name}] 掷骰结果 raw={raw_roll} total={final_total}"

    summary_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    max_lines = 3 if tool_name in {"attack_action", "cast_spell"} else 2
    summary = " | ".join(summary_lines[:max_lines])
    if not summary:
        summary = raw_text[:180] or "工具已执行。"
    if len(summary) > 180:
        summary = summary[:177] + "..."
    return f"[工具:{tool_name}] {summary}"


def _summarize_system_message(content: str) -> str:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    head = lines[0] if lines else "[系统]"
    body = " | ".join(lines[1:3])
    if body:
        return f"{head} {body}"
    return head


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


def _state_value_to_dict(value):
    """将图状态中的 Pydantic/映射对象统一转成 dict。"""
    if value is None:
        return None
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value)


def _all_players_down(combat_dict: dict, player_dict: dict | None) -> bool:
    """检查战场上是否已不存在存活的玩家单位。"""
    from app.services.tools._helpers import get_all_combatants

    all_combatants = get_all_combatants(combat_dict, player_dict)
    player_units = [unit for unit in all_combatants.values() if unit.get("side") == "player"]
    if not player_units:
        return False
    return all(unit.get("hp", 0) <= 0 for unit in player_units)


def _build_combat_system_message(log_lines: list[str], attack_roll: dict | None = None) -> HumanMessage:
    """把节点内的怪物/反应结算统一投影成系统战报消息。"""
    from app.services.tools._helpers import build_attack_roll_event_payload

    combat_report = "[系统:怪物行动]\n" + "\n".join(log_lines)
    message_kwargs = {}
    if attack_roll is not None:
        attack_roll_payload = build_attack_roll_event_payload(attack_roll)
        if attack_roll_payload:
            message_kwargs["additional_kwargs"] = {
                "attack_roll": attack_roll_payload,
            }
    return HumanMessage(content=combat_report, **message_kwargs)


def _build_player_death_summary(messages: list[BaseMessage]) -> str:
    """玩家团灭时优先复用最近一次真实战报，而不是再造一份占位文本。"""
    for message in reversed(messages):
        content = _message_content_to_text(getattr(message, "content", "")).strip()
        if content:
            return content
    return "[系统:怪物行动]\n所有玩家单位已倒下！"


def combat_resolution_node(state: GraphState) -> dict:
    """战斗后置收束节点：统一处理玩家团灭 interrupt，不再依赖旧 monster 节点。"""
    from langgraph.types import interrupt

    combat_dict = _state_value_to_dict(state.get("combat"))
    if not combat_dict:
        return {}

    player_dict = _state_value_to_dict(state.get("player"))
    if not _all_players_down(combat_dict, player_dict):
        return {}

    user_choice = interrupt({
        "type": "player_death",
        "summary": _build_player_death_summary(state.get("messages", [])),
        "hp_changes": list(state.get("hp_changes", [])),
    })

    if player_dict:
        if user_choice == "revive":
            player_dict["hp"] = max(1, player_dict.get("max_hp", 1) // 2)
        else:
            player_dict["hp"] = 0

    result_state: dict = {
        "combat": None,
        "phase": "exploration",
        "messages": [HumanMessage(content="[系统] 玩家角色倒下，战斗结束。")],
        "hp_changes": [],
        "pending_reaction": None,
        "reaction_choice": None,
    }
    if player_dict:
        result_state["player"] = player_dict

    return result_state


def resolve_reaction_node(state: GraphState) -> dict:
    """继续结算一条已暂停的怪物攻击，并应用玩家的反应选择。"""
    from app.services.tools._helpers import advance_turn, get_combatant, apply_attack_damage, compute_ac
    from app.services.tools.reactions import execute_player_reaction

    combat = state.get("combat")
    pending_reaction = state.get("pending_reaction")
    if not combat or not pending_reaction:
        return {"pending_reaction": None, "reaction_choice": None}

    combat_dict = _state_value_to_dict(combat)
    player_dict = _state_value_to_dict(state.get("player"))
    pending_dict = _state_value_to_dict(pending_reaction)
    reaction_choice = _state_value_to_dict(state.get("reaction_choice")) or {"spell_id": None}

    attacker_id = pending_dict.get("attacker_id", "")
    target_id = pending_dict.get("target_id", "")
    actor = get_combatant(combat_dict, player_dict, attacker_id)
    target = get_combatant(combat_dict, player_dict, target_id)
    if not actor or not target:
        result = {
            "combat": combat_dict,
            "pending_reaction": None,
            "reaction_choice": None,
        }
        if player_dict:
            result["player"] = player_dict
        return result

    roll_info = dict(pending_dict.get("attack_roll", {}))
    log_lines: list[str] = []
    hp_changes: list[dict] = []

    reaction_context = {
        "attacker": pending_dict.get("attacker_name", actor.get("name", attacker_id)),
        "attack_roll": {
            "raw_roll": roll_info.get("raw_roll", roll_info.get("natural", 0)),
            "attack_bonus": roll_info.get("attack_bonus", 0),
            "final_total": roll_info.get("hit_total", 0),
            "hit_total": roll_info.get("hit_total", 0),
            "target_ac": roll_info.get("target_ac", 10),
        },
    }

    chosen_spell_id = reaction_choice.get("spell_id")
    if chosen_spell_id and player_dict:
        reaction_result = execute_player_reaction(player_dict, reaction_choice, reaction_context)
        log_lines.extend(reaction_result.lines)

        if reaction_result.modifies_ac:
            new_ac = compute_ac(player_dict)
            roll_info["target_ac"] = new_ac
            if roll_info.get("natural") != 20 and roll_info.get("hit_total", 0) < new_ac:
                roll_info["hit"] = False
                roll_info["crit"] = False
                if roll_info.get("lines"):
                    roll_info["lines"][-1] = f"命中骰总值: {roll_info['hit_total']} vs AC {new_ac}（反应法术生效，未命中！）"
            elif roll_info.get("lines"):
                if roll_info.get("natural") == 20:
                    detail = "天然 20，反应法术无法改判！"
                else:
                    detail = "反应法术生效，但仍然命中！"
                roll_info["lines"][-1] = f"命中骰总值: {roll_info['hit_total']} vs AC {new_ac}（{detail}）"
    else:
        log_lines.append("你放弃了反应。")

    atk_lines, _, hp_change, _ = apply_attack_damage(actor, target, roll_info)
    log_lines.extend(atk_lines)
    if hp_change:
        hp_changes.append(hp_change)

    turn_text = advance_turn(combat_dict, player_dict)
    log_lines.append(turn_text)

    result_state: dict = {
        "combat": combat_dict,
        "messages": [_build_combat_system_message(log_lines, attack_roll=roll_info)],
        "hp_changes": hp_changes,
        "pending_reaction": None,
        "reaction_choice": None,
    }
    if player_dict:
        result_state["player"] = player_dict
    return result_state
