"""单证处理业务规则：该填哪些项、什么时候能流转，整个模块只在这里定义一份。

页面与校验接口共用同一份判断：接口直接引用下方常量，
页面通过 GET /api/manifest/rules 读取 RULES，两边结论永远同源。
"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "manifest"
FIELDS = ["单证编号", "单证类型", "关联航次", "申报箱量", "申报人", "提交时间", "审核人员", "单证状态"]
REQUIRED_FIELDS = ["单证编号", "单证类型", "关联航次"]
STATUS_ORDER = ["待提交", "已提交", "已审核", "已退回"]
ACTION_RULES = {"提交单证": "已提交", "审核通过": "已审核", "退回单证": "已退回"}
NEGATIVE_ACTIONS: list[str] = []

RULES: dict[str, Any] = {
    "module": MODULE,
    "fields": FIELDS,
    "required_fields": REQUIRED_FIELDS,
    "statuses": STATUS_ORDER,
    "actions": [
        {"name": name, "target": target, "abnormal": name in NEGATIVE_ACTIONS}
        for name, target in ACTION_RULES.items()
    ],
}


class ManifestService:
    def rules(self) -> dict[str, Any]:
        """单证录入与流转判断的唯一出口，页面与接口都从这里取结论。"""
        return RULES

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

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
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
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"单证已{action}"
