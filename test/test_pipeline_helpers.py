"""pipeline 辅助函数的代码级单测（pytest 版）。

对照 rag/tests/ 下的脚本式验证：这里用 pytest 的 assert + parametrize，
失败退出码非零可直接进 CI 拦截。
运行：.venv/bin/pytest test/test_pipeline_helpers.py -v
"""
import pytest

from AiLearning.capabilities.pipeline import _collect_rule_ids


def _tools(content: str) -> list[dict]:
    """构造一次 loop 的 write_output 工具调用记录。"""
    return [{"name": "write_output", "args": {"content": content}}]


def test_collect_rule_ids_merges_and_dedups():
    tools = _tools('[{"rule_ids": ["R1", "R2"]}, {"rule_ids": ["R2", "R3"]}]')
    assert _collect_rule_ids(tools) == {"R1", "R2", "R3"}


def test_collect_rule_ids_ignores_non_write_output():
    tools = [{"name": "rag_search", "args": {"content": '[{"rule_ids": ["R9"]}]'}}]
    assert _collect_rule_ids(tools) == set()


@pytest.mark.parametrize("content,expected", [
    ('[{"rule_ids": ["R1"]}]', {"R1"}),   # 正常单条
    ('[]', set()),                        # 空数组
    ('not-json', set()),                  # 非法 JSON 容错
    ('[{"rule_ids": null}]', set()),      # 空 rule_ids 容错
    ('[{"no_rule_ids": 1}]', set()),      # 缺字段容错
])
def test_collect_rule_ids_edge_cases(content, expected):
    assert _collect_rule_ids(_tools(content)) == expected
