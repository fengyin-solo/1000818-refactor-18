"""单证处理业务规则：状态流转、字段校验与筛选口径都收在这里。

页面与接口共用这一份判断：
- 必填项与可填项看 REQUIRED_FIELDS（create_entry 与 rules_view 同源）；
- 什么状态能做什么动作看 FLOW_RULES（run_action 与 rules_view 同源）。
不要在路由层或前端再抄一份常量。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "manifest"
REQUIRED_FIELDS = ["单证编号", "单证类型", "关联航次"]
STATUS_ORDER = ["待提交", "已提交", "已审核", "已退回"]
ACTION_RULES = {"提交单证": "已提交", "审核通过": "已审核", "退回单证": "已退回"}
NEGATIVE_ACTIONS = []
# 每个动作只允许从列出的源状态发起；没列到的状态一律不能流转。
FLOW_RULES = {
    "提交单证": ["待提交"],
    "审核通过": ["已提交"],
    "退回单证": ["已提交"],
}


class ManifestService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("单证编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def rules_view(self) -> dict[str, Any]:
        """对外下发的规则视图：页面按它渲染表单与动作按钮，接口按同样常量裁决。"""
        return {
            "form_fields": list(REQUIRED_FIELDS),
            "required_fields": list(REQUIRED_FIELDS),
            "statuses": list(STATUS_ORDER),
            "initial_status": STATUS_ORDER[0],
            "transitions": [
                {
                    "action": action,
                    "target": ACTION_RULES[action],
                    "from_statuses": list(FLOW_RULES.get(action, [])),
                }
                for action in ACTION_RULES
            ],
        }

    def missing_fields(self, values: dict[str, Any]) -> list[str]:
        return [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]

    def actions_for(self, status: str | None) -> list[str]:
        """某状态下页面可放行的动作，顺序与 ACTION_RULES 保持一致。"""
        return [action for action, allowed in FLOW_RULES.items() if status in allowed]

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = self.missing_fields(values)
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"单证 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于单证处理可执行范围"
        current = str(entry.get("status") or "")
        if current not in FLOW_RULES.get(action, []):
            return None, f"当前状态「{current}」下不允许执行动作「{action}」"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"单证已{action}"
