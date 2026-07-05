"""XMind 格式转换器。

XMind 2020+ 文件是 zip 包，内含 content.json。

导入: XMind 树 → list[TestCase]
  树形: Root → 类型节点 → 用例节点 → (前置/步骤/预期 子节点)
  每个用例节点及其子节点合并为一条 TestCase

导出: list[TestCase] → XMind 文件
  按 type 分组，构建树形结构
"""

from __future__ import annotations

import json
import uuid
import zipfile
from pathlib import Path

from AiLearning.utils.converters.base import BaseConverter, Format, TestCase


class XMindConverter(BaseConverter):
    readable = Format.XMIND
    writable = Format.XMIND

    # ── 导入: XMind → list[TestCase] ──

    def import_data(self, source: str | Path, **options) -> list[TestCase]:
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(f"文件不存在: {source}")

        with zipfile.ZipFile(source) as z:
            content = json.loads(z.read("content.json"))

        sheet = content[0]
        root = sheet["rootTopic"]
        cases: list[TestCase] = []

        # 一级节点 = 用例类型
        for type_node in root.get("children", {}).get("attached", []):
            type_name = type_node.get("title", "")
            # 二级节点 = 用例
            for case_node in type_node.get("children", {}).get("attached", []):
                case = self._parse_case_node(case_node, type_name)
                if case:
                    cases.append(case)

        return cases

    @staticmethod
    def _parse_case_node(node: dict, type_name: str) -> TestCase | None:
        """从 XMind 用例节点提取字段。"""
        title = node.get("title", "")
        # 解析 "TC-001: 标题" 格式
        case_id = ""
        case_title = title
        if ": " in title or "：" in title:
            sep = ": " if ": " in title else "："
            case_id, case_title = title.split(sep, 1)

        precondition = ""
        steps: list[str] = []
        expected = ""

        children = node.get("children", {}).get("attached", [])
        for child in children:
            ct = child.get("title", "")
            if ct.startswith("前置") or ct.startswith("前提"):
                precondition = _extract_after_colon(ct)
            elif ct.startswith("预期") or ct.startswith("期望"):
                expected = _extract_after_colon(ct)
            elif ct.startswith("步骤"):
                # 收集步骤子节点
                step_children = child.get("children", {}).get("attached", [])
                for sc in step_children:
                    st = sc.get("title", "")
                    steps.append(st)
            elif ct.startswith("前置条件") or ct.startswith("前提条件"):
                precondition = _extract_after_colon(ct)
            elif ct.startswith("预期结果") or ct.startswith("期望结果"):
                expected = _extract_after_colon(ct)

        return TestCase(
            id=case_id,
            title=case_title,
            type=type_name,
            precondition=precondition,
            steps=steps,
            expected=expected,
        )

    # ── 导出: list[TestCase] → XMind ──

    def export_data(
        self,
        cases: list[TestCase],
        target: str | Path,
        **options,
    ) -> Path:
        target = Path(target)
        title = options.get("title", "测试用例")
        root = _make_topic(title)
        root_children: list[dict] = []

        groups: dict[str, list[TestCase]] = {}
        for tc in cases:
            groups.setdefault(tc.type, []).append(tc)

        for type_name, type_cases in groups.items():
            type_node = _make_topic(f"{type_name}（{len(type_cases)}条）")
            type_children: list[dict] = []

            for tc in type_cases:
                case_node = _make_topic(f"{tc.id}: {tc.title}")
                case_children: list[dict] = []

                if tc.precondition:
                    case_children.append(_make_topic(f"前置条件: {tc.precondition}"))
                if tc.steps:
                    steps_node = _make_topic("测试步骤")
                    step_items = [
                        _make_topic(f"步骤{i}: {s}") if not s.startswith(f"{i}.") and not s.startswith(f"{i}、")
                        else _make_topic(s)
                        for i, s in enumerate(tc.steps, 1)
                    ]
                    steps_node["children"] = {"attached": step_items}
                    case_children.append(steps_node)
                if tc.expected:
                    case_children.append(_make_topic(f"预期结果: {tc.expected}"))

                case_node["children"] = {"attached": case_children}
                type_children.append(case_node)

            type_node["children"] = {"attached": type_children}
            root_children.append(type_node)

        root["children"] = {"attached": root_children}

        sheet = {
            "id": str(uuid.uuid4()),
            "title": title,
            "rootTopic": root,
        }

        return _write_xmind_zip(sheet, title, target)


# ═══════════════════════════════════════════════════════════════
# 内部辅助
# ═══════════════════════════════════════════════════════════════

def _make_topic(title: str) -> dict:
    return {"id": str(uuid.uuid4()), "title": title}


def _extract_after_colon(text: str) -> str:
    """提取冒号后的内容。"""
    for sep in (": ", "：", ":", "："):
        if sep in text:
            return text.split(sep, 1)[1].strip()
    return text


def _write_xmind_zip(sheet: dict, title: str, output: Path) -> Path:
    """将 sheet 写入 .xmind 文件。"""
    output.parent.mkdir(parents=True, exist_ok=True)
    safe_name = title.replace("/", "_").replace(" ", "_")
    filepath = output.parent / f"{safe_name}.xmind"

    with zipfile.ZipFile(filepath, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("content.json", json.dumps([sheet], ensure_ascii=False))
        z.writestr(
            "metadata.xml",
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<meta xmlns="urn:xmind:xmap:xmlns:meta:2.0" version="2.0"/>',
        )
        z.writestr(
            "manifest.json",
            json.dumps({"file-entries": {"content.json": {}, "metadata.xml": {}}}, ensure_ascii=False),
        )

    return filepath
