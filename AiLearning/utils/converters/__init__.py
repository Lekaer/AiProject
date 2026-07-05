"""用例格式转换器 — 可扩展的格式转换框架。

统一入口:
  convert(source, to_fmt)                                → 导入并转换
  convert_agent_output(cases, to_fmt, target, **options)  → 导出

当前支持: XMind ↔ Agent JSON ↔ TXT | Agent JSON → MD
新增格式: 新建 Converter 子类，在 registry.py 中注册即可。
"""

from __future__ import annotations

from pathlib import Path

from AiLearning.utils.converters.base import Format, TestCase
from AiLearning.utils.converters.registry import get_converter, list_formats


def _dicts_to_cases(data: list[dict]) -> list[TestCase]:
    return [TestCase.from_dict(d) for d in data]


def _cases_to_dicts(cases: list[TestCase]) -> list[dict]:
    return [tc.to_dict() for tc in cases]


# ── 导入: XMind/TXT → Agent JSON / TXT ──

def convert_to_cases(source: str | Path, from_fmt: str) -> list[dict]:
    """从指定格式导入用例，返回 Agent JSON（list[dict]）。

    用法:
      cases = convert_to_cases("用例.xmind", from_fmt="xmind")
      # => [{"id": "TC-001", "title": "...", ...}, ...]
    """
    fmt = Format(from_fmt)
    converter = get_converter(readable=fmt)
    testcases = converter.import_data(source)
    return _cases_to_dicts(testcases)


def convert_to_text(source: str | Path, from_fmt: str, **options) -> str:
    """从指定格式导入用例，返回结构化文本（用于上传 KB 作为参考用例）。

    用法:
      text = convert_to_text("用例.xmind", from_fmt="xmind", title="商户入驻参考用例")
      # 上传到 KB 供 Agent 使用
    """
    fmt = Format(from_fmt)
    converter = get_converter(readable=fmt)
    return converter.import_as_text(source, **options)


# ── 导出: Agent JSON → XMind / MD / TXT ──

def convert_agent_output(
    cases: list[dict],
    to_fmt: str,
    target: str | Path,
    **options,
) -> Path:
    """将 Agent 生成的用例 JSON 导出为指定格式文件。

    用法:
      # XMind
      path = convert_agent_output(cases, to_fmt="xmind", target="./output", title="批量入驻用例")
      # => ./output/批量入驻用例.xmind

      # Markdown
      path = convert_agent_output(cases, to_fmt="md", target="./output", title="批量入驻用例")
      # => ./output/批量入驻用例.md
    """
    fmt = Format(to_fmt)
    converter = get_converter(writable=fmt)
    testcases = _dicts_to_cases(cases)
    return converter.export_data(testcases, target, **options)
