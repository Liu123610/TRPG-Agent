"""护盾术 (Shield) — 1环防护，反应动作 AC+5"""

from app.spells._base import SpellDef, SpellResult

SPELL_DEF: SpellDef = {
    "name": "Shield",
    "name_cn": "护盾术",
    "level": 1,
    "school": "abjuration",
    "casting_time": "reaction",
    "range": "self",
    "description": "反应动作施放，直到下一回合开始前AC+5。",
}


def execute(caster: dict, targets: list[dict], slot_level: int, **_) -> SpellResult:
    """施法者 AC+5 直到下一回合开始，通过 shield_active 条件标记追踪"""
    # targets[0] 就是施法者本体（"self" 解析结果）
    target = targets[0]
    caster_name = caster.get("name", "?")

    old_ac = target.get("ac", 10)
    new_ac = old_ac + 5
    target["ac"] = new_ac

    conditions = target.setdefault("conditions", [])
    if "shield_active" not in conditions:
        conditions.append("shield_active")

    lines = [
        f"{caster_name} 施放 护盾术!",
        f"AC: {old_ac} → {new_ac}（持续到下一回合开始）",
    ]

    return {"lines": lines}
