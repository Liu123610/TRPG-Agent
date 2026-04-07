# backend/app/graph/state.py
from typing import Annotated, Literal, Optional, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


# 角色六维能力值（通常用于检定基础值）
AbilityBlock = TypedDict(
    "AbilityBlock",
    {
        "str": int,
        "dex": int,
        "con": int,
        "int": int,
        "wis": int,
        "cha": int,
    },
    total=False,
)

# 六维对应修正值（通常由能力值推导）
ModifierBlock = TypedDict(
    "ModifierBlock",
    {
        "str": int,
        "dex": int,
        "con": int,
        "int": int,
        "wis": int,
        "cha": int,
    },
    total=False,
)


# 玩家常驻状态
class PlayerState(TypedDict, total=False):
    name: str
    role_class: str
    level: int
    hp: int
    max_hp: int
    temp_hp: int
    ac: int
    abilities: AbilityBlock
    modifiers: ModifierBlock
    conditions: list[str]          # e.g. ["poisoned", "prone"]
    resources: dict[str, int]      # e.g. {"spell_slot_lv1": 2}


# 待执行的一次检定请求
class CheckState(TypedDict, total=False):
    kind: Literal["attack", "skill", "save", "custom"]
    ability: Literal["str", "dex", "con", "int", "wis", "cha"]
    dc: int
    target: Optional[str]
    advantage: Literal["normal", "advantage", "disadvantage"]


# 最近一次掷骰结果
class RollResultState(TypedDict, total=False):
    dice: str                      # e.g. "1d20"
    raw: int
    modifier: int
    total: int
    success: bool


# 战斗单位快照（玩家/敌人/友方）
class CombatantState(TypedDict, total=False):
    id: str
    name: str
    side: Literal["player", "enemy", "ally"]
    hp: int
    max_hp: int
    ac: int
    conditions: list[str]


# 整个 LangGraph 在节点间传递的共享状态
class GraphState(TypedDict, total=False):
    # --- 核心对话流程字段 ---
    messages: Annotated[list[AnyMessage], add_messages]
    output: str

    conversation_summary: str          # 持久的大纲记忆
    session_id: str                    # 会话唯一标识

    # --- 扩展领域字段（当前 chat 主链路未启用） ---
    phase: Literal["exploration", "combat", "resolution"]
    turn_index: int                # 当前回合序号

    scene_summary: str             # 场景摘要，减少长上下文重复
    player: PlayerState

    pending_check: Optional[CheckState]      # 等待掷骰解析的检定
    last_roll: Optional[RollResultState]     # 最近一次检定/攻击结果

    in_combat: bool
    round: int
    combatants: list[CombatantState]

    event_log: list[dict]          # 记录关键事件，便于回放/调试
