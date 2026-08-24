"""通用文本格式转换器 — LLM 驱动的自由格式导入。

读取任意 MD/TXT 文件，通过 LLM 识别并提取为规范 TestCase 列表。
规则解析器（MarkdownConverter）作为备选保留。
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from AiLearning.prompts.generic_import import DEFAULT_GENERIC_IMPORT_PROMPT
from AiLearning.service import get_client
from AiLearning.utils.converters.base import BaseConverter, Format, TestCase

logger = logging.getLogger(__name__)


class GenericTextConverter(BaseConverter):
    """LLM 驱动的通用格式转换器。

    import: 任意 MD/TXT → LLM 提取 → list[TestCase]
    export:  list[TestCase] → MD 文件
    """

    readable = Format.TXT
    writable = Format.MD

    def import_data(self, source: str | Path, **options) -> list[TestCase]:
        """从任意文本格式文档中提取用例。"""
        source = Path(source)
        text = source.read_text(encoding="utf-8") if source.exists() else str(source)

        if not text.strip():
            return []

        prompt = DEFAULT_GENERIC_IMPORT_PROMPT.format(document=text)
        client = get_client()
        response = client.chat(
            messages=[
                {"role": "system", "content": DEFAULT_GENERIC_IMPORT_PROMPT.system},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            max_tokens=8192,
        )

        items = _parse_json_list(response)
        return [TestCase.from_dict(item) for item in items]

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


def _parse_json_list(raw: str) -> list[dict]:
    """从 LLM 响应中安全提取 JSON 对象列表。"""
    text = raw.strip()

    # 1) 直接解析
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    # 2) markdown code fence
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    # 3) 查找第一个 JSON 数组
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    logger.warning("无法从 LLM 响应中解析 JSON 数组: %s", text[:200])
    return []
