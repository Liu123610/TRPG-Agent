"""工具注册入口 — 统一导出全部 LangGraph 工具"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from langchain_core.tools import BaseTool

from app.services.tools.dice_tools import request_dice_roll
from app.services.tools.character_tools import (
    inspect_unit,
    load_character_profile,
    modify_character_state,
)
from app.services.tools.combat_tools import (
    attack_action,
    delegate_combat_turn,
    end_combat,
    manage_scene_units,
    next_turn,
    prepare_combat_end,
    prepare_combat_start,
    start_combat,
)
from app.services.tools.item_tools import buy_item, use_item
from app.services.tools.spell_tools import cast_spell
from app.services.tools.rag_tools import consult_rules_handbook
from app.services.tools.rest_tools import take_rest
from app.services.tools.space_tools import (
    create_plane_map,
    manage_space,
    measure_distance,
    move_unit,
    remove_unit,
    place_unit,
    query_units_in_radius,
)
from app.services.tools.monster_action_tools import use_monster_action
from app.services.tools.class_action_tools import use_class_action
from app.services.tools.adventure_tools import (
    advance_adventure,
    claim_adventure_reward,
    inspect_adventure_state,
    load_adventure_node,
    manage_adventure,
    mark_adventure_event,
    reveal_adventure_clue,
    search_adventure_nodes,
    switch_adventure_node,
)

# 供外部模块直接引用的战斗计算函数
from app.services.tools._helpers import (
    advance_turn,
    apply_attack_damage,
    prepare_character_for_combat,
    prepare_player_for_combat,
    resolve_single_attack,
    roll_attack_hit,
)

# 反应调度器
from app.services.tools.reactions import (
    get_available_reactions,
    build_interrupt_payload,
    execute_player_reaction,
    resolve_npc_reaction,
)

ToolProfile = Literal["narrative", "combat"]

_NARRATIVE_TOOLS: tuple[BaseTool, ...] = (
    request_dice_roll,
    load_character_profile,
    modify_character_state,
    manage_scene_units,
    prepare_combat_start,
    cast_spell,
    use_item,
    buy_item,
    use_class_action,
    inspect_unit,
    consult_rules_handbook,
    take_rest,
    manage_space,
    claim_adventure_reward,
)

_COMBAT_TOOLS: tuple[BaseTool, ...] = (
    request_dice_roll,
    modify_character_state,
    use_class_action,
    use_item,
    attack_action,
    delegate_combat_turn,
    prepare_combat_end,
    manage_scene_units,
    use_monster_action,
    next_turn,
    cast_spell,
    inspect_unit,
    consult_rules_handbook,
    manage_space,
)

_COMPATIBILITY_TOOLS: tuple[BaseTool, ...] = (
    start_combat,
    end_combat,
    manage_adventure,
    inspect_adventure_state,
    load_adventure_node,
    search_adventure_nodes,
    switch_adventure_node,
    reveal_adventure_clue,
    mark_adventure_event,
    advance_adventure,
    create_plane_map,
    place_unit,
    move_unit,
    remove_unit,
    measure_distance,
    query_units_in_radius,
)

_ALL_TOOLS: tuple[BaseTool, ...] = _NARRATIVE_TOOLS + tuple(
    tool for tool in _COMBAT_TOOLS if tool not in _NARRATIVE_TOOLS
) + tuple(
    tool for tool in _COMPATIBILITY_TOOLS if tool not in _NARRATIVE_TOOLS and tool not in _COMBAT_TOOLS
)


# 模型只看 profile，ToolNode 仍保留全量工具以执行历史调用。
@lru_cache(maxsize=None)
def get_tool_profile(profile: ToolProfile) -> list[BaseTool]:
    if profile == "narrative":
        return list(_NARRATIVE_TOOLS)
    if profile == "combat":
        return list(_COMBAT_TOOLS)
    raise ValueError(f"Unknown tool profile: {profile}")


@lru_cache(maxsize=1)
def get_tools() -> list[BaseTool]:
    return list(_ALL_TOOLS)
