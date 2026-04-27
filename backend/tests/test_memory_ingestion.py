import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.memory.episodic_store import EpisodicStore
from app.memory.ingestion import MemoryIngestionPipeline


class _FakeStore:
    def __init__(self):
        self.records = []

    async def append_record(self, **kwargs):
        self.records.append(kwargs)

    async def close(self):
        return None


class _FakeLLMService:
    def __init__(self, response: str | None = None, error: Exception | None = None):
        self._response = response or ""
        self._error = error
        self.calls: list[dict[str, str]] = []

    def invoke_summary(self, summary_input: str, *, system_prompt: str) -> str:
        self.calls.append({"summary_input": summary_input, "system_prompt": system_prompt})
        if self._error is not None:
            raise self._error
        return self._response


class MemoryIngestionPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingest_keeps_stable_events_and_filters_volatile_combat_fields(self):
        store = _FakeStore()
        pipeline = MemoryIngestionPipeline(store)

        await pipeline.ingest(
            session_id="demo",
            turn_id="turn-1",
            old_state={
                "player": {
                    "name": "英雄",
                    "role_class": "法师",
                    "resources": {"spell_slot_lv1": 2},
                    "conditions": [],
                },
                "combat": None,
                "dead_units": {},
            },
            new_state={
                "player": {
                    "name": "英雄",
                    "role_class": "法师",
                    "resources": {"spell_slot_lv1": 1},
                    "conditions": [{"id": "shield_active"}],
                    "hp": 7,
                    "movement_left": 0,
                    "action_available": False,
                },
                "combat": {"round": 1, "initiative_order": ["player_hero", "goblin_1"], "participants": {"goblin_1": {}}},
                "dead_units": {},
            },
            new_messages=[
                ToolMessage(content="英雄施放护盾术。", tool_call_id="call_1", name="cast_spell"),
                AIMessage(content="护盾展开，挡住了下一次攻击。", tool_calls=[]),
            ],
            reply="护盾展开，挡住了下一次攻击。",
        )

        kinds = [record["record_kind"] for record in store.records]
        self.assertEqual(["turn_messages", "stable_events", "turn_summary"], kinds)

        stable_events = store.records[1]["payload"]["events"]
        event_types = [event["type"] for event in stable_events]
        self.assertIn("resource_update", event_types)
        self.assertIn("condition_update", event_types)
        self.assertIn("combat_started", event_types)

        serialized = str(stable_events)
        self.assertNotIn("movement_left", serialized)
        self.assertNotIn("action_available", serialized)
        self.assertNotIn("initiative_order", serialized)
        self.assertNotIn("hp", serialized)

        turn_summary = store.records[2]["payload"]["summary"]
        self.assertIn("资源变更", turn_summary)
        self.assertIn("主持人回应", turn_summary)

    async def test_fetch_recent_summaries_only_reads_turn_summary_records(self):
        with TemporaryDirectory() as temp_dir:
            store = EpisodicStore(str(Path(temp_dir) / "episodic.sqlite3"))

            await store.append_record(
                session_id="demo",
                turn_id="turn-1",
                record_kind="turn_summary",
                payload={"summary": "主持人回应：你们已经发现地牢密门。"},
            )
            await store.append_record(
                session_id="demo",
                turn_id="turn-2",
                record_kind="stable_events",
                payload={
                    "events": [
                        {
                            "type": "resource_update",
                            "changes": [{"key": "spell_slot_lv1", "old": 2, "new": 1}],
                        }
                    ]
                },
            )
            await store.append_record(
                session_id="demo",
                turn_id="turn-3",
                record_kind="turn_summary",
                payload={"summary": "主持人回应：哥布林已经举起短弓。"},
            )

            summaries = await store.fetch_recent_summaries("demo")
            await store.close()

        self.assertEqual(
            [
                "主持人回应：你们已经发现地牢密门。",
                "主持人回应：哥布林已经举起短弓。",
            ],
            summaries,
        )

    async def test_combat_end_turn_summary_prefers_archived_combat_summary(self):
        store = _FakeStore()
        pipeline = MemoryIngestionPipeline(store)

        await pipeline.ingest(
            session_id="demo",
            turn_id="turn-2",
            old_state={
                "player": {
                    "name": "英雄",
                    "resources": {"spell_slot_lv1": 2},
                    "conditions": [],
                },
                "combat": {"round": 3, "participants": {"goblin_1": {}}},
                "combat_archives": [],
                "dead_units": {},
            },
            new_state={
                "player": {
                    "name": "英雄",
                    "resources": {"spell_slot_lv1": 1},
                    "conditions": [{"id": "shield_active"}],
                },
                "combat": None,
                "combat_archives": [
                    {
                        "summary": "英雄在 3 回合内击败两只哥布林，消耗 1 个 1 环法术位并维持护盾。",
                        "start_index": 2,
                        "end_index": 8,
                    }
                ],
                "dead_units": {"goblin_1": {}, "goblin_2": {}},
            },
            new_messages=[
                ToolMessage(content="共进行了 3 回合。 存活: 英雄 倒下: Goblin, Goblin", tool_call_id="call_1", name="end_combat"),
                AIMessage(content="你甩掉剑上的血迹，确认周围暂时安全。", tool_calls=[]),
            ],
            reply="你甩掉剑上的血迹，确认周围暂时安全。",
        )

        turn_summary = store.records[2]["payload"]["summary"]
        self.assertIn("战斗摘要：英雄在 3 回合内击败两只哥布林", turn_summary)
        self.assertNotIn("主持人回应", turn_summary)
        self.assertNotIn("工具结果", turn_summary)

    async def test_ingest_uses_model_to_compress_turn_summary_without_repeating_hud_state(self):
        store = _FakeStore()
        fake_llm = _FakeLLMService(response="英雄击败哥布林并消耗 1 个 1 环法术位，现场暂时安全。")

        with TemporaryDirectory() as temp_dir:
            pipeline = MemoryIngestionPipeline(store, llm_service=fake_llm, trace_dir=Path(temp_dir))

            await pipeline.ingest(
                session_id="demo",
                turn_id="turn-3",
                old_state={
                    "phase": "combat",
                    "player": {
                        "name": "英雄",
                        "resources": {"spell_slot_lv1": 2},
                        "conditions": [],
                    },
                    "combat": {"round": 2, "participants": {"goblin_1": {}}},
                    "combat_archives": [],
                    "dead_units": {},
                },
                new_state={
                    "phase": "exploration",
                    "player": {
                        "name": "英雄",
                        "resources": {"spell_slot_lv1": 1},
                        "conditions": [{"id": "shield_active"}],
                        "hp": 7,
                        "movement_left": 0,
                        "action_available": False,
                    },
                    "combat": None,
                    "combat_archives": [
                        {
                            "summary": "英雄在 2 回合内击败哥布林，消耗 1 个 1 环法术位并维持护盾。",
                            "start_index": 1,
                            "end_index": 5,
                        }
                    ],
                    "dead_units": {"goblin_1": {}},
                },
                new_messages=[
                    ToolMessage(content="共进行了 2 回合。 存活: 英雄 倒下: Goblin", tool_call_id="call_1", name="end_combat"),
                    AIMessage(content="你确认周围暂时安全。", tool_calls=[]),
                ],
                reply="你确认周围暂时安全。",
            )

        self.assertEqual("英雄击败哥布林并消耗 1 个 1 环法术位，现场暂时安全。", store.records[2]["payload"]["summary"])
        self.assertEqual(1, len(fake_llm.calls))
        self.assertIn("不要重复 HUD 已提供的当前玩家状态", fake_llm.calls[0]["system_prompt"])
        self.assertNotIn("movement_left", fake_llm.calls[0]["summary_input"])
        self.assertNotIn("action_available", fake_llm.calls[0]["summary_input"])

    async def test_ingest_falls_back_to_rule_summary_when_model_summary_fails(self):
        store = _FakeStore()
        fake_llm = _FakeLLMService(error=RuntimeError("summary failed"))

        with TemporaryDirectory() as temp_dir:
            pipeline = MemoryIngestionPipeline(store, llm_service=fake_llm, trace_dir=Path(temp_dir))

            await pipeline.ingest(
                session_id="demo",
                turn_id="turn-4",
                old_state={
                    "phase": "exploration",
                    "player": {"name": "英雄", "resources": {}, "conditions": []},
                    "combat": None,
                    "combat_archives": [],
                    "dead_units": {},
                },
                new_state={
                    "phase": "exploration",
                    "player": {"name": "英雄", "resources": {}, "conditions": []},
                    "combat": None,
                    "combat_archives": [],
                    "dead_units": {},
                },
                new_messages=[AIMessage(content="石门背后传来锁链拖动声。", tool_calls=[])],
                reply="石门背后传来锁链拖动声。",
            )

        turn_summary = store.records[1]["payload"]["summary"]
        self.assertEqual("主持人回应：石门背后传来锁链拖动声。", turn_summary)


if __name__ == "__main__":
    unittest.main()