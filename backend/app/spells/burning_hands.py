"""燃烧之手 (Burning Hands) — 1环塑能，锥形 AoE + DEX 豁免"""

import d20

from app.spells._base import SpellDef, SpellResult, get_spell_dc

SPELL_DEF: SpellDef = {
    "name": "Burning Hands",
    "name_cn": "燃烧之手",
    "level": 1,
    "school": "evocation",
    "casting_time": "action",
    "range": "self (15-foot cone)",
    "description": "15尺锥形区域，目标DEX豁免，失败受3d6火焰伤害，成功减半。升环+1d6。",
}


def execute(caster: dict, targets: list[dict], slot_level: int, **_) -> SpellResult:
    """3d6 火焰伤害（升环+1d6），DEX 豁免成功减半"""
    dice_count = 3 + (slot_level - 1)
    formula = f"{dice_count}d6"

    dmg_roll = d20.roll(formula)
    full_damage = max(1, dmg_roll.total)
    half_damage = full_damage // 2

    spell_dc = get_spell_dc(caster)
    caster_name = caster.get("name", "?")

    lines = [
        f"{caster_name} 施放 燃烧之手（{slot_level}环）— DC {spell_dc} DEX 豁免",
        f"伤害骰: {dmg_roll} = {full_damage} 火焰伤害",
    ]
    hp_changes: list[dict] = []

    for target in targets:
        target_name = target.get("name", "?")
        dex_mod = target.get("modifiers", {}).get("dex", 0)
        save_roll = d20.roll(f"1d20+{dex_mod}")
        saved = save_roll.total >= spell_dc

        actual_damage = half_damage if saved else full_damage
        save_text = f"豁免成功({save_roll})" if saved else f"豁免失败({save_roll})"

        lines.append(f"  → {target_name}: {save_text} — {actual_damage} 火焰伤害")

        old_hp = target.get("hp", 0)
        new_hp = max(0, old_hp - actual_damage)
        target["hp"] = new_hp

        hp_changes.append({
            "id": target.get("id", ""),
            "name": target_name,
            "old_hp": old_hp,
            "new_hp": new_hp,
            "max_hp": target.get("max_hp", old_hp),
        })
        lines.append(f"  {target_name} HP: {old_hp} → {new_hp}")
        if new_hp == 0:
            lines.append(f"  {target_name} 倒下了!")

    return {"lines": lines, "hp_changes": hp_changes}
