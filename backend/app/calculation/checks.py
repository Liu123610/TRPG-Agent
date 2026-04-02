# 检定计算模块
from typing import Literal, Optional
from app.graph.state import CheckState, RollResultState, AbilityBlock
from app.calculation.dice import roll_d20
from app.calculation.abilities import get_ability_modifier
from app.calculation.proficiency import calculate_proficiency_bonus

# 执行D&D检定
def perform_check(
    check: CheckState,
    abilities: AbilityBlock,
    level: int = 1,
    has_proficiency: bool = False,
    additional_modifiers: int = 0
) -> RollResultState:
    """
    执行D&D检定
    """
    # 获取基础修正值
    ability_modifier = get_ability_modifier(abilities, check["ability"])
    proficiency_bonus = calculate_proficiency_bonus(level) if has_proficiency else 0

    # 计算总修正值
    total_modifier = ability_modifier + proficiency_bonus + additional_modifiers

    # 投掷d20（考虑优势/劣势）
    advantage = check.get("advantage", "normal")
    if advantage not in ["normal", "advantage", "disadvantage"]:
        advantage = "normal"
    raw_roll = roll_d20(advantage)

    # 计算总值
    total = raw_roll + total_modifier

    # 判断成功/失败
    dc = check.get("dc", 10)
    success = total >= dc

    return RollResultState(
        dice="1d20",
        raw=raw_roll,
        modifier=total_modifier,
        total=total,
        success=success
    )

# 攻击检定
def perform_attack_check(
    attacker_abilities: AbilityBlock,
    level: int = 1,
    weapon_type: Literal["melee", "ranged", "finesse", "thrown"] = "melee",
    weapon_enhancement: int = 0,  # 魔法武器增强值（+1, +2等）
    has_proficiency: bool = False,
    advantage: Literal["normal", "advantage", "disadvantage"] = "normal"
) -> RollResultState:
    """
    执行攻击检定（遵循D&D 5e规则）
    根据D&D 5e规则：
    - 近战武器使用力量属性
    - 弓/弩等物理远程武器使用敏捷属性
    - 投掷武器（飞斧、飞刀等）使用力量属性
    - 灵巧武器可选择力量或敏捷中较高者
    - 武器增强值（魔法武器）是额外加成，不是替换属性修正
    """
    # 根据武器类型选择能力修正值
    if weapon_type == "ranged":
        # 物理远程武器（弓、弩、火枪等）使用敏捷
        ability_modifier = get_ability_modifier(attacker_abilities, "dex")
        used_ability = "dex"
    elif weapon_type == "thrown":
        # 投掷武器（飞斧、飞刀、投掷长矛等）使用力量
        ability_modifier = get_ability_modifier(attacker_abilities, "str")
        used_ability = "str"
    elif weapon_type == "finesse":
        # 灵巧武器可以选择力量或敏捷中较高者
        str_mod = get_ability_modifier(attacker_abilities, "str")
        dex_mod = get_ability_modifier(attacker_abilities, "dex")
        if str_mod >= dex_mod:
            ability_modifier = str_mod
            used_ability = "str"
        else:
            ability_modifier = dex_mod
            used_ability = "dex"
    else:
        # 默认近战武器使用力量
        ability_modifier = get_ability_modifier(attacker_abilities, "str")
        used_ability = "str"

    # 计算正确的熟练加值（根据等级动态计算）
    proficiency_bonus = calculate_proficiency_bonus(level) if has_proficiency else 0

    # 总修正值 = 能力修正值 + 熟练加值 + 武器增强值（魔法武器+1等）
    total_modifier = ability_modifier + proficiency_bonus + weapon_enhancement

    # 投掷攻击检定
    raw_roll = roll_d20(advantage)
    total = raw_roll + total_modifier

    result = RollResultState(
        dice="1d20",
        raw=raw_roll,
        modifier=total_modifier,
        total=total,
        success=False  # 攻击是否成功需要在combat模块中判断
    )

    # 添加使用的属性信息，供伤害计算使用
    result["used_ability"] = used_ability
    return result

# 豁免检定
def perform_saving_throw(
    abilities: AbilityBlock,
    ability: Literal["str", "dex", "con", "int", "wis", "cha"],
    dc: int,
    level: int = 1,
    has_proficiency: bool = False,
    advantage: Literal["normal", "advantage", "disadvantage"] = "normal"
) -> RollResultState:
    """
    执行豁免检定
    """
    ability_modifier = get_ability_modifier(abilities, ability)
    proficiency_bonus = calculate_proficiency_bonus(level) if has_proficiency else 0
    total_modifier = ability_modifier + proficiency_bonus

    # 投掷豁免检定
    raw_roll = roll_d20(advantage)
    total = raw_roll + total_modifier
    success = total >= dc

    return RollResultState(
        dice="1d20",
        raw=raw_roll,
        modifier=total_modifier,
        total=total,
        success=success
    )

# 技能检定
def perform_skill_check(
    abilities: AbilityBlock,
    skill: str,
    dc: int,
    level: int = 1,
    has_proficiency: bool = False,
    expertise: bool = False,  # 专家熟练（双倍熟练加值）
    advantage: Literal["normal", "advantage", "disadvantage"] = "normal"
) -> RollResultState:
    """
    执行技能检定
    """
    # 技能对应的能力值
    skill_abilities = {
        "acrobatics": "dex",
        "animal_handling": "wis",
        "arcana": "int",
        "athletics": "str",
        "deception": "cha",
        "history": "int",
        "insight": "wis",
        "intimidation": "cha",
        "investigation": "int",
        "medicine": "wis",
        "nature": "int",
        "perception": "wis",
        "performance": "cha",
        "persuasion": "cha",
        "religion": "int",
        "sleight_of_hand": "dex",
        "stealth": "dex",
        "survival": "wis"
    }

    ability = skill_abilities.get(skill.lower(), "dex")
    ability_modifier = get_ability_modifier(abilities, ability)

    # 计算熟练加值（根据等级动态计算）
    base_proficiency = calculate_proficiency_bonus(level) if has_proficiency else 0
    final_proficiency = base_proficiency * 2 if expertise else base_proficiency
    total_modifier = ability_modifier + final_proficiency

    # 投掷技能检定
    raw_roll = roll_d20(advantage)
    total = raw_roll + total_modifier
    success = total >= dc

    return RollResultState(
        dice="1d20",
        raw=raw_roll,
        modifier=total_modifier,
        total=total,
        success=success
    )

# 计算被动检定值
def calculate_passive_check(
    abilities: AbilityBlock,
    ability: Literal["str", "dex", "con", "int", "wis", "cha"],
    level: int = 1,
    has_proficiency: bool = False
) -> int:
    """
    计算被动检定值（常用于被动感知等）
    基础值: 10 + 能力修正值 + 熟练加值（如果熟练）
    """
    ability_modifier = get_ability_modifier(abilities, ability)
    proficiency = calculate_proficiency_bonus(level) if has_proficiency else 0
    return 10 + ability_modifier + proficiency