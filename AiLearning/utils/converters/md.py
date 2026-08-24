"""Markdown 格式转换器（示例：未来新增格式只需照此模式实现即可）。"""

from __future__ import annotations

from pathlib import Path

from AiLearning.utils.converters.base import BaseConverter, Format, TestCase


class MarkdownConverter(BaseConverter):
    """将用例列表导出为可读 Markdown 文档。"""

    readable = Format.TXT        # 可从 TXT/MD 文本导入（简单行解析）
    writable = Format.MD

    def import_data(self, source: str | Path, **options) -> list[TestCase]:
        """从 Markdown 文本导入——解析结构化标题还原用例。"""
        source = Path(source)
        text = source.read_text(encoding="utf-8") if source.exists() else str(source)

        cases: list[TestCase] = []
        current_type = ""
        current_case: TestCase | None = None

        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("## "):
                current_type = stripped[3:]
            elif stripped.startswith("- ") and ": " in stripped:
                title_part = stripped[2:]
                case_id, case_title = title_part.split(": ", 1)
                if current_case:
                    cases.append(current_case)
                current_case = TestCase(id=case_id, title=case_title, type=current_type)
            elif stripped.startswith("  - ") and current_case:
                detail = stripped[4:]
                if detail.startswith("前置条件:") or detail.startswith("前置条件："):
                    current_case.precondition = _after_colon(detail)
                elif detail.startswith("预期结果:") or detail.startswith("预期结果："):
                    current_case.expected = _after_colon(detail)
            elif stripped.startswith("    ") and current_case:
                step = stripped[4:]
                if step and step[0].isdigit():
                    current_case.steps.append(step)

        if current_case:
            cases.append(current_case)

        return cases

    def export_data(
        self,
        cases: list[TestCase],
        target: str | Path,
        **options,
    ) -> Path:
        """导出为 Markdown 文件。"""
        target = Path(target)
        title = options.pop("title", "测试用例")
        text = self._cases_to_text(cases, title=title, **options)
        target.parent.mkdir(parents=True, exist_ok=True)
        safe_name = title.replace("/", "_").replace(" ", "_")
        filepath = target.parent / f"{safe_name}.md"
        filepath.write_text(text, encoding="utf-8")
        return filepath


def _after_colon(text: str) -> str:
    for sep in (": ", "：", ":", "："):
        if sep in text:
            return text.split(sep, 1)[1].strip()
    return text
