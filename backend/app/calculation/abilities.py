# 角色能力值计算模块
from typing import Literal
from app.graph.state import AbilityBlock, ModifierBlock

# 能力值到修正值的转换
def ability_to_modifier(score: int) -> int:
    """
    将能力值转换为修正值（D&D 5e标准）
    公式: (能力值 - 10) // 2
    """
    return (score - 10) // 2

# 计算完整修正值块
def calculate_modifiers(abilities: AbilityBlock) -> ModifierBlock:
    """
    从能力值块计算修正值块
    """
    modifiers: ModifierBlock = {}
    for ability, score in abilities.items():
        if isinstance(score, int):
            modifiers[ability] = ability_to_modifier(score)
    return modifiers

# 获取特定能力的修正值
def get_ability_modifier(abilities: AbilityBlock, ability: Literal["str", "dex", "con", "int", "wis", "cha"]) -> int:
    """
    获取特定能力的修正值
    """
    score = abilities.get(ability, 10)
    return ability_to_modifier(score)

# 计算被动感知（常用于察觉检定）
def calculate_passive_perception(abilities: AbilityBlock, proficiency_bonus: int = 0, has_proficiency: bool = False) -> int:
    """
    计算被动感知值
    基础值: 10 + 感知修正值 + 熟练加值（如果熟练）
    """
    wis_modifier = get_ability_modifier(abilities, "wis")
    proficiency = proficiency_bonus if has_proficiency else 0
    return 10 + wis_modifier + proficiency

# 验证能力值范围
def validate_ability_scores(abilities: AbilityBlock, allow_magical: bool = True) -> bool:
    """
    验证能力值是否在有效范围内
    allow_magical: 是否允许魔法增强的超高能力值
    """
    for ability, score in abilities.items():
        if not isinstance(score, int):
            return False
        if allow_magical:
            # 允许魔法增强，但最低仍为3
            if score < 3:
                return False
        else:
            # 严格范围：3-20
            if score < 3 or score > 20:
                return False
    return True

# 计算能力值提升
def increase_ability_score(abilities: AbilityBlock, ability: Literal["str", "dex", "con", "int", "wis", "cha"], amount: int = 1) -> AbilityBlock:
    """
    提升特定能力值，返回新的能力值块
    """
    new_abilities = abilities.copy()
    current_score = new_abilities.get(ability, 10)
    new_score = min(20, current_score + amount)  # 上限为20
    new_abilities[ability] = new_score
    return new_abilities