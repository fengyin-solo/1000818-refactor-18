"""单证规则同源性测试：service 是唯一事实源，页面与接口消费同一份结论。

只依赖标准库，直接调用 service；接口路由通过 app.routes 校验已注册。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.manifest import (  # noqa: E402
    ACTION_RULES,
    FLOW_RULES,
    REQUIRED_FIELDS,
    STATUS_ORDER,
    ManifestService,
)
from app.store import store  # noqa: E402


class ManifestRulesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.service = ManifestService()
        self.rules = self.service.rules_view()

    def test_rules_view_is_consistent_with_constants(self) -> None:
        self.assertEqual(self.rules["form_fields"], REQUIRED_FIELDS)
        self.assertEqual(self.rules["required_fields"], REQUIRED_FIELDS)
        self.assertEqual(self.rules["statuses"], STATUS_ORDER)
        self.assertEqual(self.rules["initial_status"], STATUS_ORDER[0])
        self.assertEqual(
            [item["action"] for item in self.rules["transitions"]],
            list(ACTION_RULES),
        )
        for item in self.rules["transitions"]:
            self.assertEqual(item["target"], ACTION_RULES[item["action"]])
            self.assertEqual(item["from_statuses"], FLOW_RULES[item["action"]])
            self.assertIn(item["target"], STATUS_ORDER)
            for status in item["from_statuses"]:
                self.assertIn(status, STATUS_ORDER)

    def test_actions_for_matches_rules_view(self) -> None:
        for status in STATUS_ORDER:
            allowed = {
                item["action"]
                for item in self.rules["transitions"]
                if status in item["from_statuses"]
            }
            self.assertEqual(set(self.service.actions_for(status)), allowed)

    def test_create_validation_uses_same_required_fields(self) -> None:
        entry, missing = self.service.create_entry({})
        self.assertIsNone(entry)
        self.assertEqual(missing, REQUIRED_FIELDS)

        values = {field: f"值-{field}" for field in REQUIRED_FIELDS}
        entry, missing = self.service.create_entry(values)
        self.assertEqual(missing, [])
        self.assertIsNotNone(entry)
        self.assertEqual(entry["status"], self.rules["initial_status"])

    def test_flow_preconditions_and_historical_conclusions(self) -> None:
        values = {field: f"流转-{field}" for field in REQUIRED_FIELDS}
        entry, _ = self.service.create_entry(values)
        entry_id = int(entry["id"])

        # 待提交只能提交；审核通过/退回都被拦下
        self.assertIsNone(self.service.run_action(entry_id, "审核通过")[0])
        self.assertIsNone(self.service.run_action(entry_id, "退回单证")[0])
        entry, message = self.service.run_action(entry_id, "提交单证")
        self.assertEqual(entry["status"], "已提交")
        self.assertTrue(entry["pending"])
        self.assertEqual(message, "单证已提交单证")

        # 已提交不能重复提交
        self.assertIsNone(self.service.run_action(entry_id, "提交单证")[0])

        # 退回结论与历史写法一致：已退回、pending=False、abnormal=False
        entry, _ = self.service.run_action(entry_id, "退回单证")
        self.assertEqual(entry["status"], "已退回")
        self.assertFalse(entry["pending"])
        self.assertFalse(entry["abnormal"])

        # 终态后任何动作都不再放行
        for action in ACTION_RULES:
            self.assertIsNone(self.service.run_action(entry_id, action)[0])

    def test_approve_conclusion_unchanged(self) -> None:
        # 走完整流程后审核通过：结论必须与改造前完全一致。
        # 注：pending 的历史口径是「目标状态 != 序列末位（已退回）」，故已审核仍为 True，保持不变。
        values = {field: f"审核-{field}" for field in REQUIRED_FIELDS}
        entry, _ = self.service.create_entry(values)
        entry_id = int(entry["id"])
        self.service.run_action(entry_id, "提交单证")
        entry, message = self.service.run_action(entry_id, "审核通过")
        self.assertEqual(entry["status"], "已审核")
        self.assertTrue(entry["pending"])
        self.assertFalse(entry["abnormal"])
        self.assertEqual(message, "单证已审核通过")

    def test_unknown_action_still_rejected(self) -> None:
        entry, message = self.service.run_action(1, "不存在的动作")
        self.assertIsNone(entry)
        self.assertIn("不属于单证处理可执行范围", message)

    def test_seed_data_untouched(self) -> None:
        rows = store.rows("manifest")
        self.assertEqual(
            [(row["id"], row["status"]) for row in rows[:3]],
            [(1, "待提交"), (2, "已提交"), (3, "已审核")],
        )

    def test_rules_route_registered_before_wildcard(self) -> None:
        # 环境无 FastAPI 运行时，路由顺序按源码静态校验：/rules 必须在 /{entry_id} 之前注册
        router_source = (Path(__file__).resolve().parents[1] / "app" / "routers" / "manifest.py").read_text(encoding="utf-8")

        def index_of(pattern: str) -> int:
            index = router_source.find(pattern)
            self.assertGreaterEqual(index, 0, pattern)
            return index

        self.assertLess(index_of('"/rules"'), index_of('"/{entry_id}"'))
        self.assertIn("service.rules_view()", router_source)
        self.assertNotIn("STATUSES =", router_source)


if __name__ == "__main__":
    unittest.main()
