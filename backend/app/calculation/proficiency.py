# 熟练加值计算模块

def calculate_proficiency_bonus(level: int) -> int:
    """
    根据角色等级计算熟练加值（D&D 5e标准）
    等级 1-4: +2
    等级 5-8: +3
    等级 9-12: +4
    等级 13-16: +5
    等级 17-20: +6
    """
    if level < 1:
        return 0
    elif level <= 4:
        return 2
    elif level <= 8:
        return 3
    elif level <= 12:
        return 4
    elif level <= 16:
        return 5
    else:
        return 6

# 计算熟练项总数（用于角色创建平衡）
def calculate_total_proficiencies(level: int, role_class: str) -> dict[str, int]:
    """
    根据职业和等级计算各类熟练项数量（遵循D&D 5e官方规则）
    返回: {"skills": 技能数, "tools": 工具数, "languages": 语言数}
    """
    # 根据D&D 5e官方规则设置各职业的熟练项
    class_proficiencies = {
        "barbarian": {"skills": 2, "tools": 1, "languages": 1},
        "bard": {"skills": 3, "tools": 0, "languages": 2},  # 诗人初始3技能，2语言，无等级加成
        "cleric": {"skills": 2, "tools": 0, "languages": 1},
        "druid": {"skills": 2, "tools": 1, "languages": 1},
        "fighter": {"skills": 2, "tools": 1, "languages": 1},
        "monk": {"skills": 2, "tools": 0, "languages": 1},
        "paladin": {"skills": 2, "tools": 0, "languages": 1},
        "ranger": {"skills": 3, "tools": 1, "languages": 1},
        "rogue": {"skills": 4, "tools": 1, "languages": 1},
        "sorcerer": {"skills": 2, "tools": 0, "languages": 1},
        "warlock": {"skills": 2, "tools": 1, "languages": 1},
        "wizard": {"skills": 2, "tools": 0, "languages": 1}
    }

    # 返回指定职业的熟练项，如果没有则返回默认值
    return class_proficiencies.get(role_class.lower(), {"skills": 2, "tools": 1, "languages": 1})

# 计算豁免熟练项
def get_saving_throw_proficiencies(role_class: str) -> list[str]:
    """
    根据职业返回熟练的豁免类型
    """
    saving_throws = {
        "barbarian": ["str", "con"],
        "bard": ["dex", "cha"],
        "cleric": ["wis", "cha"],
        "druid": ["int", "wis"],
        "fighter": ["str", "con"],
        "monk": ["str", "dex"],
        "paladin": ["str", "cha"],  # 修正：圣骑士是力量+魅力，不是感知+魅力
        "ranger": ["str", "dex"],
        "rogue": ["dex", "int"],
        "sorcerer": ["con", "cha"],
        "warlock": ["wis", "cha"],
        "wizard": ["int", "wis"]
    }
    return saving_throws.get(role_class.lower(), [])

# 计算技能熟练项
def get_skill_proficiencies(role_class: str) -> list[str]:
    """
    根据职业返回可选的技能熟练项（示例）
    """
    class_skills = {
        "barbarian": ["animal handling", "athletics", "intimidation", "nature", "perception", "survival"],
        "bard": ["acrobatics", "animal handling", "arcana", "athletics", "deception", "history", "insight", "intimidation", "investigation", "medicine", "nature", "perception", "performance", "persuasion", "religion", "sleight of hand", "stealth", "survival"],
        "cleric": ["history", "insight", "medicine", "persuasion", "religion"],
        "druid": ["arcana", "animal handling", "insight", "medicine", "nature", "perception", "religion", "survival"],
        "fighter": ["acrobatics", "animal handling", "athletics", "history", "insight", "intimidation", "perception", "survival"],
        "monk": ["acrobatics", "athletics", "history", "insight", "religion", "stealth"],
        "paladin": ["athletics", "insight", "intimidation", "medicine", "persuasion", "religion"],
        "ranger": ["animal handling", "athletics", "insight", "investigation", "nature", "perception", "stealth", "survival"],
        "rogue": ["acrobatics", "athletics", "deception", "insight", "intimidation", "investigation", "perception", "performance", "persuasion", "sleight of hand", "stealth"],
        "sorcerer": ["arcana", "athletics", "deception", "insight", "intimidation", "persuasion", "religion"],
        "warlock": ["arcana", "deception", "history", "intimidation", "investigation", "nature", "religion"],
        "wizard": ["arcana", "history", "insight", "investigation", "medicine", "religion"]
    }
    return class_skills.get(role_class.lower(), [])