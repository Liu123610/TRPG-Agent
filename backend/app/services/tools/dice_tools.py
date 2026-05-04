"""掷骰工具"""

from __future__ import annotations

from typing import Annotated, Literal

import d20
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState


@tool
def request_dice_roll(
    reason: str,
    state: Annotated[dict, InjectedState],
    ability: Literal["str", "dex", "con", "int", "wis", "cha"] | None = None,
    formula: str = "1d20"
) -> dict:
    """向玩家发起掷骰请求以判断动作结果（例如："破门力量检定"）。
    如果提供了 `ability` 参数，系统会自动获取对应角色的属性值，并计算修正附加到总分中。
    注意：你在接下来的叙事中绝对不需要（也不应该）手动二次加上修正值计算结果，因为本工具返回的 final_total 已经包含了修正值！

    Args:
        reason: 掷骰的叙事原因，例如 "破门力量检定"。
        ability: 【强烈推荐】动作所依赖的属性 ("str", "dex", "con", "int", "wis", "cha")。
        formula: 掷骰公式，默认为 "1d20"。
    """
    modifier = 0
    if ability and state.get("player") and "modifiers" in state["player"]:
        modifier = state["player"]["modifiers"].get(ability, 0)

    result = d20.roll(formula)
    raw_roll = result.total
    final_total = raw_roll + modifier

    sign = '+' if modifier >= 0 else ''
    modifier_str = f"属性修正({ability}){sign}{modifier}" if ability else "无属性修正"

    note_str = (
        f"系统已完成严谨计算：基础骰值(raw_roll)={raw_roll}，"
        f"{modifier_str}，最终总值(final_total)={final_total}。\n"
        "【特别指令】：请向玩家如实播报这个算式（例：\"基础X + 修正Y = 最终Z\"），并严格仅使用 final_total 判断检定成败，不要自己重新做加法！"
    )

    return {
        "raw_roll": raw_roll,
        "modifier": modifier,
        "final_total": final_total,
        "status": "success",
        "note": note_str
    }
