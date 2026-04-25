import unittest
from types import SimpleNamespace
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.services.chat_session_service import ChatSessionService


class FakeGraph:
    def __init__(self, result: dict):
        self.result = result
        self.last_input = None
        self.last_config = None
        self.values = {"messages": []}
        self.tasks = []

    async def ainvoke(self, graph_input, config):
        self.last_input = graph_input
        self.last_config = config
        self.values = self.result
        return self.result

    async def aget_state(self, config):
        self.last_config = config
        return SimpleNamespace(values=self.values, tasks=self.tasks)


class ChatSessionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_turn_returns_last_non_tool_ai_message(self):
        graph = FakeGraph(
            {
                "messages": [
                    AIMessage(content="", tool_calls=[{"name": "weather", "args": {"city": "beijing"}, "id": "call_1"}]),
                    AIMessage(content="北京今天晴，22C。", tool_calls=[]),
                ]
            }
        )
        service = ChatSessionService(graph=graph)

        result = await service.process_turn(message="北京天气怎么样", session_id="s1")

        self.assertEqual("北京今天晴，22C。", result["reply"])
        self.assertEqual("s1", result["session_id"])
        self.assertIsNone(result["plan"])
        self.assertEqual("s1", graph.last_config["configurable"]["thread_id"])
        self.assertEqual("北京天气怎么样", graph.last_input["messages"][0].content)

    async def test_process_turn_generates_session_id_when_missing(self):
        graph = FakeGraph({"messages": [AIMessage(content="ok", tool_calls=[])]})
        service = ChatSessionService(graph=graph)

        result = await service.process_turn(message="hello")

        UUID(result["session_id"])
        self.assertEqual(result["session_id"], graph.last_config["configurable"]["thread_id"])

    async def test_get_history_keeps_original_transcript_without_tool_placeholders(self):
        graph = FakeGraph({"messages": []})
        graph.values = {
            "messages": [
                HumanMessage(content="我攻击哥布林"),
                AIMessage(content="", tool_calls=[{"name": "attack_action", "args": {"attacker_id": "player_hero"}, "id": "call_1"}]),
                ToolMessage(content="Goblin 使用 [Scimitar] 攻击 英雄!\n英雄 HP: 18 → 13", tool_call_id="call_1", name="attack_action"),
                HumanMessage(content="[系统:怪物行动]\n你放弃了反应。"),
                AIMessage(content="哥布林被你逼退了半步。", tool_calls=[]),
            ]
        }
        service = ChatSessionService(graph=graph)

        history = await service.get_history(session_id="demo", limit=10)

        self.assertEqual(
            [
                {"role": "user", "content": "我攻击哥布林"},
                {"role": "assistant", "content": "哥布林被你逼退了半步。"},
            ],
            history["messages"],
        )
        self.assertFalse(any("[工具:" in item["content"] for item in history["messages"]))
        self.assertFalse(any("实时系统监控窗" in item["content"] for item in history["messages"]))


if __name__ == "__main__":
    unittest.main()
