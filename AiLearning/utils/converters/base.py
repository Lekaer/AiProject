"""转换器基类。

所有格式转换器以 Agent JSON（list[dict]）为中间规范格式：
  导入路径: 任意格式 → Agent JSON → 序列化为目标格式
  导出路径: Agent JSON → 任意格式
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Format(str, Enum):
    XMIND = "xmind"
    JSON = "json"
    TXT = "txt"
    MD = "md"
    CSV = "csv"


@dataclass
class TestCase:
    """中间规范格式的单条用例。"""
    id: str
    title: str
    type: str                              # 用例类型，对应 Skill display_name
    precondition: str = ""
    steps: list[str] = field(default_factory=list)
    expected: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "type": self.type,
            "precondition": self.precondition,
            "steps": self.steps,
            "expected": self.expected,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TestCase":
        return cls(
            id=d.get("id", ""),
            title=d.get("title", ""),
            type=d.get("type", ""),
            precondition=d.get("precondition", ""),
            steps=d.get("steps", []),
            expected=d.get("expected", ""),
        )


class BaseConverter(ABC):
    """格式转换器基类。

    子类只需实现两个方法：
      - import_data: 外部格式 → list[TestCase]
      - export_data: list[TestCase] → 外部格式文件

    新增格式：新建一个 Converter 子类，注册到 registry 即可。
    """

    # 子类声明自己支持的类型
    readable: Format       # 可从哪种格式导入
    writable: Format       # 可导出为哪种格式

    # ── 导入 ──

    @abstractmethod
    def import_data(self, source: str | Path, **options) -> list[TestCase]:
        """从外部格式文件导入，返回规范用例列表。"""
        ...

    # ── 导出 ──

    @abstractmethod
    def export_data(
        self,
        cases: list[TestCase],
        target: str | Path,
        **options,
    ) -> Path:
        """将规范用例列表导出为指定格式，返回输出文件路径。"""
        ...

    # ── 便捷方法 ──

    def import_as_text(self, source: str | Path, **options) -> str:
        """导入并转为结构化文本（用于 KB 上传）。"""
        cases = self.import_data(source, **options)
        return self._cases_to_text(cases, **options)

    @staticmethod
    def _cases_to_text(cases: list[TestCase], title: str = "参考用例", **options) -> str:
        """将规范用例列表序列化为结构化文本。"""
        if not cases:
            return ""

        groups: dict[str, list[TestCase]] = {}
        for tc in cases:
            groups.setdefault(tc.type, []).append(tc)

        lines = [f"# {title}", ""]
        for type_name, type_cases in groups.items():
            lines.append(f"## {type_name}")
            for tc in type_cases:
                lines.append(f"- {tc.id}: {tc.title}")
                if tc.precondition:
                    lines.append(f"  - 前置条件: {tc.precondition}")
                if tc.steps:
                    lines.append(f"  - 步骤:")
                    for i, s in enumerate(tc.steps, 1):
                        lines.append(f"    {i}. {s}")
                if tc.expected:
                    lines.append(f"  - 预期结果: {tc.expected}")
                lines.append("")
        return "\n".join(lines)
