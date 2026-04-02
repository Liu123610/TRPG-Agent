# 骰子投掷核心模块
import random
from typing import Literal
from app.graph.state import RollResultState

# 基础掷骰函数
def roll_dice(num_dice: int, sides: int) -> int:
    """
    基础骰子投掷
    num_dice: 骰子数量
    sides: 骰子面数
    """
    total = 0
    for _ in range(num_dice):
        total += random.randint(1, sides)
    return total

# d20专用检定掷骰（D&D核心）
def roll_d20(advantage: Literal["normal", "advantage", "disadvantage"] = "normal") -> int:
    """
    优势/劣势 掷骰
    advantage: normal(普通), advantage(优势), disadvantage(劣势)
    """
    roll1 = random.randint(1, 20)
    if advantage == "normal":
        return roll1

    roll2 = random.randint(1, 20)
    if advantage == "advantage":
        return max(roll1, roll2)
    return min(roll1, roll2)

# 解析骰子表达式 (e.g. "2d6+3")
def parse_dice_notation(dice_notation: str) -> tuple[int, int, int]:
    """
    解析骰子表达式
    返回: (骰子数量, 面数, 修正值)
    """
    import re
    # 匹配 "XdY+Z" 或 "XdY-Z" 格式
    pattern = r'^(\d+)d(\d+)([+-]\d+)?$'
    match = re.match(pattern, dice_notation.strip())

    if not match:
        raise ValueError(f"无效的骰子表达式: {dice_notation}")

    num_dice = int(match.group(1))
    sides = int(match.group(2))
    modifier_str = match.group(3)
    modifier = int(modifier_str) if modifier_str else 0

    return num_dice, sides, modifier

# 投掷骰子并返回标准结果
def roll_with_notation(dice_notation: str) -> RollResultState:
    """
    使用骰子表达式进行投掷并返回标准结果
    """
    num_dice, sides, modifier = parse_dice_notation(dice_notation)

    raw = roll_dice(num_dice, sides)
    total = raw + modifier

    return RollResultState(
        dice=dice_notation,
        raw=raw,
        modifier=modifier,
        total=total,
        success=False  # 需要在check模块中设置
    )