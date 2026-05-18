"""探索式 Agent 自测 CLI。

这个脚本让 Codex 或开发者像真实玩家一样逐轮和主 Agent 对话：
发送自然语言、读取真实图状态、观察 workflow 帧与工具轨迹，再临场决定下一步。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
PLAYTEST_DIR = ROOT_DIR / "logs" / "agent_playtests"
CURRENT_SESSION_FILE = PLAYTEST_DIR / "current_session.json"

# 中文注释：playtest 使用项目真实配置；当前项目默认 PostgreSQL，便于前端和数据库直接复查对话。
os.environ.setdefault("TRPG_AGENT_TRACE_DIR", str(ROOT_DIR / "logs" / "agent_traces"))

# 中文注释：Windows 终端默认 GBK 时会被模型回复里的符号打断，测试脚本统一用 UTF-8 输出。
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage  # noqa: E402
from app.graph.constants import ROUTER_NODE  # noqa: E402

from app.config.settings import settings  # noqa: E402
from app.graph.builder import build_graph  # noqa: E402
from app.memory.checkpointer import close_checkpointer, get_checkpointer  # noqa: E402
from app.services.chat_session_service import ChatSessionService  # noqa: E402
from app.utils.asyncio_policy import configure_windows_selector_event_loop_policy  # noqa: E402


configure_windows_selector_event_loop_policy()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _ensure_playtest_dir() -> None:
    PLAYTEST_DIR.mkdir(parents=True, exist_ok=True)


def _load_current_session() -> str | None:
    if not CURRENT_SESSION_FILE.exists():
        return None
    data = json.loads(CURRENT_SESSION_FILE.read_text(encoding="utf-8"))
    return str(data.get("session_id") or "") or None


def _save_current_session(session_id: str) -> None:
    _ensure_playtest_dir()
    CURRENT_SESSION_FILE.write_text(
        json.dumps({"session_id": session_id, "updated_at": _now_iso()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _resolve_session_id(value: str | None, *, create: bool = True) -> str:
    if value:
        session_id = value
    else:
        session_id = _load_current_session() or (f"playtest-{uuid4()}" if create else "")
    if session_id:
        _save_current_session(session_id)
    return session_id


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, BaseMessage):
        data = {
            "type": value.__class__.__name__,
            "content": value.content,
            "name": getattr(value, "name", None),
            "id": getattr(value, "id", None),
        }
        if isinstance(value, ToolMessage):
            data["tool_call_id"] = value.tool_call_id
        tool_calls = getattr(value, "tool_calls", None)
        if tool_calls:
            data["tool_calls"] = tool_calls
        return data
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return str(value)


def _message_label(message: BaseMessage) -> str:
    if isinstance(message, HumanMessage):
        return "Human"
    if isinstance(message, AIMessage):
        return "AI"
    if isinstance(message, ToolMessage):
        return f"Tool:{message.name or 'tool'}"
    return message.__class__.__name__


def _text(value: Any, limit: int = 1200) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = json.dumps(_jsonable(value), ensure_ascii=False)
    value = value.strip()
    return value if len(value) <= limit else value[:limit] + "...[truncated]"


def _message_content(message: BaseMessage, limit: int = 1200) -> str:
    return _text(getattr(message, "content", ""), limit=limit)


def _state_values(state: Any) -> dict[str, Any]:
    if state is None or not hasattr(state, "values"):
        return {}
    return dict(state.values or {})


async def _build_service() -> ChatSessionService:
    graph = build_graph(checkpointer=await get_checkpointer(settings))
    return ChatSessionService(graph=graph)


async def _get_state(service: ChatSessionService, session_id: str) -> dict[str, Any]:
    state = await service._graph.aget_state(service._graph_config(session_id))
    return _state_values(state)


def _test_fighter_player() -> dict[str, Any]:
    """给探索式测试提供最小可战斗角色，避免空会话先卡在建卡流程。"""
    return {
        "id": "player_hero",
        "name": "测试战士",
        "side": "player",
        "role_class": "fighter",
        "level": 1,
        "hp": 14,
        "max_hp": 14,
        "base_ac": 16,
        "ac": 16,
        "speed": 30,
        "abilities": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
        "modifiers": {"str": 3, "dex": 1, "con": 2, "int": 0, "wis": 0, "cha": 0},
        "weapons": [
            {
                "name": "Longsword",
                "damage_dice": "1d8",
                "damage_type": "slashing",
                "weapon_type": "melee",
                "reach_feet": 5,
                "attack_bonus": 5,
                "damage_bonus": 3,
            }
        ],
        "inventory": [{"id": "healing_potion", "name": "治疗药水", "quantity": 1}],
        "coins": {},
        "xp": 0,
    }


async def _seed_empty_session(service: ChatSessionService, session_id: str) -> bool:
    """空探针会话先写入根状态，避免运行时增量更新缺少 as_node。"""
    values = await _get_state(service, session_id)
    if values.get("messages") or values.get("phase") or values.get("player"):
        return False
    seed_update = {
        "session_id": session_id,
        "phase": "exploration",
        "messages": [
            HumanMessage(content=(
                "[系统:探索式测试初始化]\n"
                "当前会话由 Codex 作为测试玩家驱动。测试者会自然语言推进流程；"
                "必要时可直接将玩家回满血，以免早期死亡导致战斗 workflow 无法测完。"
            )),
        ],
        "player": _test_fighter_player(),
        "scene_units": {},
        "dead_units": {},
        "departed_units": {},
    }
    await service._graph.aupdate_state(service._graph_config(session_id), seed_update, as_node=ROUTER_NODE)
    return True


async def _build_seeded_service(session_id: str) -> ChatSessionService:
    service = await _build_service()
    await _seed_empty_session(service, session_id)
    return service


def _latest_messages(values: dict[str, Any], limit: int) -> list[BaseMessage]:
    return list(values.get("messages", []) or [])[-limit:]


def _tool_calls_from_message(message: BaseMessage) -> list[dict[str, Any]]:
    return list(getattr(message, "tool_calls", None) or [])


def _summarize_values(values: dict[str, Any], *, message_limit: int = 8) -> dict[str, Any]:
    combat = _jsonable(values.get("combat")) or None
    player = _jsonable(values.get("player")) or None
    space = _jsonable(values.get("space")) or None
    scene_units = _jsonable(values.get("scene_units")) or None
    dead_units = _jsonable(values.get("dead_units")) or None
    departed_units = _jsonable(values.get("departed_units")) or None
    messages = _latest_messages(values, message_limit)

    current_actor = None
    if isinstance(combat, dict):
        current_id = combat.get("current_actor_id")
        participants = combat.get("participants") or {}
        current_actor = participants.get(current_id)
        if current_actor is None and isinstance(player, dict) and player.get("id") == current_id:
            current_actor = player

    return {
        "phase": values.get("phase"),
        "player": _compact_unit(player) if isinstance(player, dict) else None,
        "combat": _compact_combat(combat) if isinstance(combat, dict) else None,
        "current_actor": _compact_unit(current_actor) if isinstance(current_actor, dict) else None,
        "space": _compact_space(space) if isinstance(space, dict) else None,
        "scene_units": sorted((scene_units or {}).keys()) if isinstance(scene_units, dict) else [],
        "dead_units": sorted((dead_units or {}).keys()) if isinstance(dead_units, dict) else [],
        "departed_units": sorted((departed_units or {}).keys()) if isinstance(departed_units, dict) else [],
        "recent_messages": [_compact_message(message) for message in messages],
        "recent_tool_calls": _recent_tool_calls(messages),
        "workflow_frames": _recent_workflow_frames(messages),
    }


def _compact_unit(unit: dict[str, Any] | None) -> dict[str, Any] | None:
    if not unit:
        return None
    return {
        "id": unit.get("id"),
        "name": unit.get("name"),
        "side": unit.get("side"),
        "hp": unit.get("hp"),
        "max_hp": unit.get("max_hp"),
        "ac": unit.get("ac") or unit.get("base_ac"),
        "conditions": unit.get("conditions") or [],
        "action_available": unit.get("action_available"),
        "bonus_action_available": unit.get("bonus_action_available"),
        "reaction_available": unit.get("reaction_available"),
        "movement_left": unit.get("movement_left"),
        "control_mode": unit.get("control_mode") or unit.get("controlled_by"),
        "xp": unit.get("xp"),
    }


def _compact_combat(combat: dict[str, Any]) -> dict[str, Any]:
    return {
        "round": combat.get("round"),
        "current_actor_id": combat.get("current_actor_id"),
        "initiative_order": combat.get("initiative_order"),
        "participants": {
            unit_id: _compact_unit(unit)
            for unit_id, unit in (combat.get("participants") or {}).items()
            if isinstance(unit, dict)
        },
    }


def _compact_space(space: dict[str, Any]) -> dict[str, Any]:
    active_map_id = space.get("active_map_id")
    maps = space.get("maps") or {}
    active_map = maps.get(active_map_id) if isinstance(maps, dict) else None
    return {
        "active_map_id": active_map_id,
        "active_map": active_map,
        "placements": space.get("placements") or {},
    }


def _compact_message(message: BaseMessage) -> dict[str, Any]:
    item = {
        "kind": _message_label(message),
        "content": _message_content(message, limit=700),
    }
    tool_calls = _tool_calls_from_message(message)
    if tool_calls:
        item["tool_calls"] = [
            {"name": call.get("name"), "args": call.get("args"), "id": call.get("id")}
            for call in tool_calls
        ]
    if isinstance(message, ToolMessage):
        item["tool_call_id"] = message.tool_call_id
        item["name"] = message.name
    return item


def _recent_tool_calls(messages: list[BaseMessage]) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for message in messages:
        for call in _tool_calls_from_message(message):
            calls.append({"name": call.get("name"), "args": call.get("args"), "id": call.get("id")})
    return calls


def _recent_workflow_frames(messages: list[BaseMessage]) -> list[str]:
    frames: list[str] = []
    for message in messages:
        content = _message_content(message, limit=1200)
        if content.startswith("[系统:") or "战斗执行器" in content or "战斗收束裁定" in content or "开战裁定" in content:
            frames.append(content)
    return frames[-5:]


def _print_observation(session_id: str, result: dict[str, Any] | None, values: dict[str, Any], *, message_limit: int) -> None:
    summary = _summarize_values(values, message_limit=message_limit)
    print(f"\n=== Agent Playtest Observation ===")
    print(f"session_id: {session_id}")
    print(f"phase: {summary['phase']}")
    if result is not None:
        print(f"\n[agent reply]\n{_text(result.get('reply', ''), limit=2000) or '(empty)'}")
        if result.get("pending_action"):
            print(f"\n[pending_action]\n{json.dumps(result['pending_action'], ensure_ascii=False, indent=2)}")
    print("\n[state]")
    print(json.dumps({k: v for k, v in summary.items() if k not in {"recent_messages", "workflow_frames"}}, ensure_ascii=False, indent=2))
    if summary["workflow_frames"]:
        print("\n[workflow frames]")
        for frame in summary["workflow_frames"]:
            print("- " + frame.replace("\n", "\n  "))
    print("\n[recent messages]")
    for item in summary["recent_messages"]:
        print(f"- {item['kind']}: {_text(item.get('content', ''), limit=500).replace(chr(10), ' / ')}")
        if item.get("tool_calls"):
            print(f"  tool_calls: {json.dumps(item['tool_calls'], ensure_ascii=False)}")


def _append_artifacts(session_id: str, event: dict[str, Any], values: dict[str, Any]) -> None:
    _ensure_playtest_dir()
    jsonl_path = PLAYTEST_DIR / f"{session_id}.jsonl"
    md_path = PLAYTEST_DIR / f"{session_id}.md"

    snapshot = _summarize_values(values, message_limit=10)
    record = {"at": _now_iso(), **event, "snapshot": snapshot}
    with jsonl_path.open("a", encoding="utf-8") as fp:
        fp.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    if not md_path.exists():
        md_path.write_text(f"# Agent Playtest Transcript\n\nsession_id: `{session_id}`\n\n", encoding="utf-8")

    with md_path.open("a", encoding="utf-8") as fp:
        fp.write(f"## {_now_iso()} — {event['kind']}\n\n")
        if event.get("message"):
            fp.write(f"**Player**\n\n{event['message']}\n\n")
        if event.get("reply"):
            fp.write(f"**Agent**\n\n{event['reply'] or '(empty)'}\n\n")
        if event.get("note"):
            fp.write(f"**Note**\n\n{event['note']}\n\n")
        fp.write("**Snapshot**\n\n")
        fp.write("```json\n" + json.dumps(snapshot, ensure_ascii=False, indent=2, default=str) + "\n```\n\n")


async def cmd_send(args: argparse.Namespace) -> None:
    session_id = _resolve_session_id(args.session)
    service = await _build_seeded_service(session_id)
    try:
        result = await service.process_turn(message=args.message, session_id=session_id)
        values = await _get_state(service, session_id)
        _append_artifacts(session_id, {"kind": "send", "message": args.message, "reply": result.get("reply", "")}, values)
        _print_observation(session_id, result, values, message_limit=args.messages)
    finally:
        await close_checkpointer()


async def cmd_state(args: argparse.Namespace) -> None:
    session_id = _resolve_session_id(args.session, create=False)
    if not session_id:
        raise SystemExit("No session selected. Run send --message ... first, or pass --session.")
    service = await _build_seeded_service(session_id)
    try:
        values = await _get_state(service, session_id)
        _append_artifacts(session_id, {"kind": "state", "note": "manual state inspection"}, values)
        _print_observation(session_id, None, values, message_limit=args.messages)
    finally:
        await close_checkpointer()


async def cmd_end_turn(args: argparse.Namespace) -> None:
    session_id = _resolve_session_id(args.session, create=False)
    if not session_id:
        raise SystemExit("No session selected. Run send --message ... first, or pass --session.")
    service = await _build_seeded_service(session_id)
    try:
        result = await service.end_player_controlled_turn(session_id=session_id, actor_id=args.actor_id)
        values = await _get_state(service, session_id)
        _append_artifacts(
            session_id,
            {
                "kind": "end_turn",
                "message": f"[front-end button] end turn for {args.actor_id}",
                "reply": result.get("message", ""),
            },
            values,
        )
        _print_observation(session_id, {"reply": result.get("message", ""), "pending_action": None}, values, message_limit=args.messages)
    finally:
        await close_checkpointer()


async def cmd_interactive(args: argparse.Namespace) -> None:
    session_id = _resolve_session_id(args.session)
    service = await _build_seeded_service(session_id)
    print(f"Agent playtest REPL. session_id={session_id}")
    print("Commands: /state, /end-turn <actor_id>, /session, /quit")
    try:
        while True:
            line = input("\nplayer> ").strip()
            if not line:
                continue
            if line in {"/quit", "/exit"}:
                break
            if line == "/session":
                print(session_id)
                continue
            if line == "/state":
                values = await _get_state(service, session_id)
                _append_artifacts(session_id, {"kind": "state", "note": "interactive inspection"}, values)
                _print_observation(session_id, None, values, message_limit=args.messages)
                continue
            if line.startswith("/end-turn "):
                actor_id = line.split(maxsplit=1)[1].strip()
                result = await service.end_player_controlled_turn(session_id=session_id, actor_id=actor_id)
                values = await _get_state(service, session_id)
                _append_artifacts(
                    session_id,
                    {"kind": "end_turn", "message": f"[front-end button] end turn for {actor_id}", "reply": result.get("message", "")},
                    values,
                )
                _print_observation(session_id, {"reply": result.get("message", ""), "pending_action": None}, values, message_limit=args.messages)
                continue

            result = await service.process_turn(message=line, session_id=session_id)
            values = await _get_state(service, session_id)
            _append_artifacts(session_id, {"kind": "send", "message": line, "reply": result.get("reply", "")}, values)
            _print_observation(session_id, result, values, message_limit=args.messages)
    finally:
        await close_checkpointer()


def cmd_latest(_: argparse.Namespace) -> None:
    session_id = _load_current_session()
    if not session_id:
        raise SystemExit("No current playtest session.")
    print(session_id)


def cmd_doctor(_: argparse.Namespace) -> None:
    print("Agent playtest effective config:")
    print(f"  database_backend: {settings.database_backend}")
    print(f"  memory_db_path: {settings.memory_db_path}")
    print(f"  database_url: {settings.database_url}")
    print(f"  llm_model: {settings.llm_model}")
    print(f"  llm_base_url: {settings.llm_base_url or 'default'}")
    print(f"  llm_timeout_seconds: {settings.llm_timeout_seconds}")
    print(f"  has_llm_api_key: {bool(settings.llm_api_key.strip())}")
    print(f"  artifacts_dir: {PLAYTEST_DIR}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="像真实玩家一样逐轮测试主 Agent、战斗 workflow 和执行器。",
    )
    parser.add_argument("--session", help="指定会话 ID；不传则使用最近 playtest 会话或创建新会话。")
    parser.add_argument("--messages", type=int, default=8, help="观察输出里展示的最近消息条数。")
    subparsers = parser.add_subparsers(dest="command", required=True)

    send = subparsers.add_parser("send", help="发送一条玩家自然语言输入。")
    send.add_argument("message", help="玩家输入。")

    subparsers.add_parser("state", help="读取当前图状态并记录观察。")

    end_turn = subparsers.add_parser("end-turn", help="模拟前端结束回合按钮。")
    end_turn.add_argument("actor_id", help="要结束回合的玩家或友方单位 ID。")

    subparsers.add_parser("interactive", help="进入探索式 REPL。")
    subparsers.add_parser("latest", help="打印最近 playtest session id。")
    subparsers.add_parser("doctor", help="打印探针有效配置。")
    return parser


async def async_main(args: argparse.Namespace) -> None:
    if args.command == "send":
        await cmd_send(args)
    elif args.command == "state":
        await cmd_state(args)
    elif args.command == "end-turn":
        await cmd_end_turn(args)
    elif args.command == "interactive":
        await cmd_interactive(args)
    elif args.command == "latest":
        cmd_latest(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    else:
        raise SystemExit(f"Unknown command: {args.command}")


def main() -> int:
    args = build_parser().parse_args()
    asyncio.run(async_main(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
