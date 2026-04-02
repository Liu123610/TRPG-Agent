# 战斗计算模块
from typing import Literal, Optional, Any
from app.graph.state import CombatantState, RollResultState, AbilityBlock
from app.calculation.dice import roll_dice, roll_with_notation, parse_dice_notation

# 攻击命中判定
def resolve_attack(
    attacker: CombatantState,
    defender: CombatantState,
    attack_roll: RollResultState,
    attacker_abilities: Optional[AbilityBlock] = None,
    is_ranged: bool = False,
    weapon_damage: str = "1d8",
    weapon_enhancement: int = 0
) -> dict[str, Any]:
    """
    解析攻击结果（遵循D&D 5e规则）
    """
    # 检查天然1和天然20（D&D 5e铁规则）
    natural_roll = attack_roll["raw"]

    # 天然1必失手，天然20必命中（D&D 5e核心规则）
    if natural_roll == 1:
        hit = False
        critical_hit = False
    elif natural_roll == 20:
        hit = True
        critical_hit = True
    else:
        # 正常命中判定
        hit = attack_roll["total"] >= defender["ac"]
        critical_hit = False  # 只有天然20才算暴击

    result = {
        "hit": hit,
        "critical": critical_hit,
        "attack_roll": attack_roll,
        "defender_ac": defender["ac"],
        "damage": 0,
        "damage_roll": None
    }

    # 如果命中，计算伤害
    if hit:
        weapon_type = "ranged" if is_ranged else "melee"
        used_ability = attack_roll.get("used_ability")  # 获取攻击时使用的属性
        damage_info = calculate_damage(
            attacker=attacker,
            defender=defender,
            weapon_damage=weapon_damage,
            weapon_type=weapon_type,
            weapon_enhancement=weapon_enhancement,
            attacker_abilities=attacker_abilities,
            critical_hit=critical_hit,
            used_ability=used_ability
        )
        result["damage"] = damage_info["total_damage"]
        result["damage_roll"] = damage_info["damage_roll"]

    return result

# 伤害计算
def calculate_damage(
    attacker: CombatantState,
    defender: CombatantState,
    weapon_damage: str = "1d8",
    weapon_type: Literal["melee", "ranged", "finesse", "thrown"] = "melee",
    weapon_enhancement: int = 0,  # 魔法武器增强值
    attacker_abilities: Optional[AbilityBlock] = None,
    critical_hit: bool = False,
    used_ability: Literal["str", "dex"] = None  # 攻击时使用的属性
) -> dict[str, Any]:
    """
    计算攻击伤害（遵循D&D 5e规则）
    """
    from app.calculation.abilities import get_ability_modifier

    # 解析武器伤害骰
    num_dice, sides, _ = parse_dice_notation(weapon_damage)

    # 暴击时伤害骰翻倍
    if critical_hit:
        num_dice *= 2

    # 投掷伤害骰
    damage_roll = roll_dice(num_dice, sides)

    # 根据武器类型和攻击者能力计算伤害修正值
    ability_modifier = 0
    if attacker_abilities:
        if weapon_type == "finesse" and used_ability:
            # 灵巧武器必须使用攻击时选择的同一属性（D&D 5e规则）
            ability_modifier = get_ability_modifier(attacker_abilities, used_ability)
        elif weapon_type == "ranged":
            # 远程武器（弓、弩等）使用敏捷修正值（D&D 5e规则）
            ability_modifier = get_ability_modifier(attacker_abilities, "dex")
        elif weapon_type == "thrown":
            # 投掷武器使用力量修正值
            ability_modifier = get_ability_modifier(attacker_abilities, "str")
        else:
            # 近战武器使用力量修正值
            ability_modifier = get_ability_modifier(attacker_abilities, "str")

    # 总伤害 = 伤害骰 + 能力修正值 + 武器增强值
    total_damage = damage_roll + ability_modifier + weapon_enhancement

    return {
        "damage_roll": damage_roll,
        "ability_modifier": ability_modifier,
        "weapon_enhancement": weapon_enhancement,
        "used_ability": used_ability,
        "total_damage": max(1, total_damage),  # 至少造成1点伤害
        "critical_hit": critical_hit,
        "weapon_damage": weapon_damage
    }

# 计算护甲等级(AC)
def calculate_ac(
    base_ac: int,
    dex_modifier: int,
    armor_type: Literal["none", "light", "medium", "heavy"] = "none",
    shield_bonus: int = 0,
    other_bonuses: int = 0
) -> int:
    """
    计算总护甲等级（遵循D&D 5e规则）
    """
    # 根据护甲类型应用敏捷修正值上限
    if armor_type == "heavy":
        # 重甲（链甲、板甲）：不加敏捷修正
        dex_contribution = 0
    elif armor_type == "medium":
        # 中甲（皮甲等）：敏捷最多+2
        dex_contribution = min(dex_modifier, 2)
    else:
        # 无甲或轻甲：全额敏捷修正
        dex_contribution = dex_modifier

    return base_ac + dex_contribution + shield_bonus + other_bonuses

# 先攻检定
def roll_initiative(dex_modifier: int, advantage: Literal["normal", "advantage", "disadvantage"] = "normal") -> RollResultState:
    """
    投掷先攻
    """
    from app.calculation.dice import roll_d20

    raw_roll = roll_d20(advantage)
    total = raw_roll + dex_modifier

    return RollResultState(
        dice="1d20",
        raw=raw_roll,
        modifier=dex_modifier,
        total=total,
        success=False  # 先攻没有成功/失败的概念
    )

# 战斗轮次管理
def next_combat_turn(current_round: int, current_combatant_index: int, total_combatants: int) -> tuple[int, int]:
    """
    计算下一个战斗轮次和战斗单位索引
    """
    next_index = (current_combatant_index + 1) % total_combatants
    next_round = current_round + 1 if next_index == 0 else current_round

    return next_round, next_index

# 生命值状态检查
def check_combatant_status(combatant: CombatantState) -> dict[str, any]:
    """
    检查战斗单位状态
    """
    current_hp = combatant["hp"]
    max_hp = combatant["max_hp"]

    status = {
        "alive": current_hp > 0,
        "bloodied": current_hp <= max_hp // 2,  # 血量低于一半
        "unconscious": current_hp <= 0,
        "current_hp": current_hp,
        "max_hp": max_hp,
        "hp_percentage": (current_hp / max_hp) * 100 if max_hp > 0 else 0
    }

    return status

# 应用伤害或治疗
def apply_health_change(combatant: CombatantState, change: int) -> CombatantState:
    """
    应用生命值变化（正数为治疗，负数为伤害）
    """
    new_combatant = combatant.copy()
    current_hp = new_combatant["hp"]
    max_hp = new_combatant["max_hp"]

    new_hp = current_hp + change

    # 生命值不能超过最大值，也不能低于0
    new_hp = max(0, min(new_hp, max_hp))

    new_combatant["hp"] = new_hp
    return new_combatant

# 优势/劣势条件判断
def determine_advantage(
    attacker: CombatantState,
    defender: CombatantState,
    conditions: dict[str, bool] = None
) -> Literal["normal", "advantage", "disadvantage"]:
    """
    根据战斗条件判断攻击是否有优势或劣势
    """
    if conditions is None:
        conditions = {}

    # 默认情况
    advantage_count = 0
    disadvantage_count = 0

    # 检查各种条件
    if defender.get("conditions") and "prone" in defender["conditions"]:
        advantage_count += 1  # 对倒地目标有优势

    if defender.get("conditions") and "restrained" in defender["conditions"]:
        advantage_count += 1  # 对束缚目标有优势

    if attacker.get("conditions") and "blinded" in attacker["conditions"]:
        disadvantage_count += 1  # 失明者有劣势

    if conditions.get("invisible_attacker", False):
        advantage_count += 1  # 隐形攻击者有优势

    if conditions.get("hidden_attacker", False):
        advantage_count += 1  # 隐藏攻击者有优势

    # 判断最终结果
    if advantage_count > disadvantage_count:
        return "advantage"
    elif disadvantage_count > advantage_count:
        return "disadvantage"
    else:
        return "normal"