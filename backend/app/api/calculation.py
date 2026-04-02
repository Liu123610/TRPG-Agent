# 数值计算API端点
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel

from app.services.calculation_service import CalculationService

router = APIRouter(prefix="/api/calc", tags=["calculation"])

calculator = CalculationService()

# ======================
# 请求/响应模型
# ======================

class DiceRollRequest(BaseModel):
    dice_notation: str

class DiceRollResponse(BaseModel):
    success: bool
    dice: str
    result: int
    raw: int
    modifier: int
    message: str

class SkillCheckRequest(BaseModel):
    skill: str
    dc: int
    player_data: Dict[str, Any]
    has_proficiency: bool = False
    advantage: Literal["normal", "advantage", "disadvantage"] = "normal"

class SkillCheckResponse(BaseModel):
    success: bool
    check_result: Dict[str, Any]
    message: str

class AttackRequest(BaseModel):
    attacker_data: Dict[str, Any]
    defender_data: Dict[str, Any]
    player_data: Dict[str, Any]
    is_ranged: bool = False
    weapon_damage: str = "1d8"

class AttackResponse(BaseModel):
    success: bool
    attack_result: Dict[str, Any]
    message: str

class InitiativeRequest(BaseModel):
    player_data: Dict[str, Any]

class InitiativeResponse(BaseModel):
    success: bool
    initiative_result: Dict[str, Any]
    message: str

# ======================
# API端点
# ======================

@router.post("/roll", response_model=DiceRollResponse)
async def roll_dice(request: DiceRollRequest):
    """
    投掷骰子
    """
    try:
        result = calculator.roll(request.dice_notation)
        return {
            "success": True,
            "dice": request.dice_notation,
            "result": result["total"],
            "raw": result["raw"],
            "modifier": result["modifier"],
            "message": f"投掷 {request.dice_notation}: {result['raw']} + {result['modifier']} = {result['total']}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/skill-check", response_model=SkillCheckResponse)
async def skill_check(request: SkillCheckRequest):
    """
    执行技能检定
    """
    try:
        from app.graph.state import PlayerState
        player = PlayerState(**request.player_data)
        result = calculator.perform_skill_check(
            skill=request.skill,
            dc=request.dc,
            player=player,
            has_proficiency=request.has_proficiency,
            advantage=request.advantage
        )
        return {
            "success": True,
            "check_result": result,
            "message": f"{request.skill}检定: {result['total']} vs DC{request.dc} - {'成功' if result['success'] else '失败'}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/attack", response_model=AttackResponse)
async def attack(request: AttackRequest):
    """
    执行攻击
    """
    try:
        from app.graph.state import PlayerState, CombatantState
        attacker = CombatantState(**request.attacker_data)
        defender = CombatantState(**request.defender_data)
        player = PlayerState(**request.player_data)

        result = calculator.perform_attack(
            attacker=attacker,
            defender=defender,
            player=player,
            is_ranged=request.is_ranged,
            weapon_damage=request.weapon_damage
        )

        hit_text = "命中" if result["hit"] else "未命中"
        critical_text = " (暴击!)" if result["critical"] else ""
        message = f"攻击{hit_text}{critical_text}"
        if result["hit"]:
            message += f", 造成{result['damage']}点伤害"

        return {
            "success": True,
            "attack_result": result,
            "message": message
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/initiative", response_model=InitiativeResponse)
async def initiative(request: InitiativeRequest):
    """
    投掷先攻
    """
    try:
        from app.graph.state import PlayerState
        player = PlayerState(**request.player_data)
        result = calculator.roll_initiative(player)
        return {
            "success": True,
            "initiative_result": result,
            "message": f"先攻检定: {result['total']} (d20+{result['modifier']})"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/character/{character_id}/abilities")
async def get_character_abilities(character_id: str):
    """
    获取角色能力值信息
    """
    # 这里应该从数据库获取角色数据，现在返回示例数据
    sample_abilities = {"str": 16, "dex": 14, "con": 15, "int": 12, "wis": 13, "cha": 10}
    result = calculator.calculate_ability_modifiers(sample_abilities)
    return {"success": True, "abilities": sample_abilities, "modifiers": result}

@router.get("/character/{character_id}/passive-perception")
async def get_passive_perception(character_id: str):
    """
    获取角色被动感知
    """
    # 这里应该从数据库获取角色数据，现在返回示例数据
    from app.graph.state import PlayerState
    sample_player_data = {
        "name": "Sample Hero",
        "level": 3,
        "abilities": {"str": 16, "dex": 14, "con": 15, "int": 12, "wis": 13, "cha": 10},
        "hp": 25,
        "max_hp": 25,
        "ac": 16
    }
    player = PlayerState(**sample_player_data)
    result = calculator.calculate_passive_perception(player)
    return {"success": True, "passive_perception": result}

@router.post("/combatant/status")
async def get_combatant_status(combatant_data: Dict[str, Any]):
    """
    获取战斗单位状态
    """
    try:
        from app.graph.state import CombatantState
        combatant = CombatantState(**combatant_data)
        result = calculator.get_combatant_status(combatant)
        return {"success": True, "status": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/combatant/heal")
async def heal_combatant(combatant_data: Dict[str, Any], healing_amount: int):
    """
    治疗战斗单位
    """
    try:
        from app.graph.state import CombatantState
        combatant = CombatantState(**combatant_data)
        result = calculator.heal_combatant(combatant, healing_amount)
        return {"success": True, "updated_combatant": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/combatant/damage")
async def damage_combatant(combatant_data: Dict[str, Any], damage_amount: int):
    """
    对战斗单位造成伤害
    """
    try:
        from app.graph.state import CombatantState
        combatant = CombatantState(**combatant_data)
        result = calculator.damage_combatant(combatant, damage_amount)
        return {"success": True, "updated_combatant": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/quick-roll/{dice_type}")
async def quick_roll(dice_type: int = 20, modifier: int = 0):
    """
    快速投掷骰子
    """
    try:
        result = calculator.quick_roll(dice_type, modifier)
        return {"success": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))