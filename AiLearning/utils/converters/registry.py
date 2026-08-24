"""转换器注册表，自动发现并注册所有 Converter 子类。"""

from __future__ import annotations

from AiLearning.utils.converters.base import BaseConverter, Format
from AiLearning.utils.converters.generic_text import GenericTextConverter
from AiLearning.utils.converters.xmind import XMindConverter
from AiLearning.utils.converters.md import MarkdownConverter

# 注册所有内置转换器（顺序有优先级：GenericTextConverter 优先处理 TXT 导入）
_CONVERTERS: list[BaseConverter] = [
    GenericTextConverter(),
    XMindConverter(),
    MarkdownConverter(),
]


def get_converter(*, readable: Format | None = None, writable: Format | None = None) -> BaseConverter:
    """查找可读写指定格式的转换器。MD 格式自动 fallback 到 TXT。"""
    # MD → TXT fallback：任意 MD 文件均可由 TXT 转换器处理
    if readable == Format.MD:
        readable = Format.TXT

    for c in _CONVERTERS:
        match = True
        if readable is not None and c.readable != readable:
            match = False
        if writable is not None and c.writable != writable:
            match = False
        if match:
            return c
    raise ValueError(f"找不到转换器: readable={readable}, writable={writable}")


def list_formats() -> dict[str, list[str]]:
    """列出所有已注册的导入/导出格式。"""
    importable = [c.readable.value for c in _CONVERTERS]
    exportable = [c.writable.value for c in _CONVERTERS]
    return {"import": sorted(set(importable)), "export": sorted(set(exportable))}
