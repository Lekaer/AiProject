"""对抗审查 pass（M3-2）：用例生成后的 red-team 环节。

输入：流程结构 + 该流程已生成的用例（点用例 + 场景用例的标题/预期摘要）。
输出：覆盖缺口报告（write_output 落盘 review_<flow_id>.json）。

攻击方法论维护在 skills/red_team/SKILL.md（registry: false，不进生成目录），
本模块直接读取其正文注入 prompt——审查是单一方法论，无需渐进式披露。
"""

import glob
import json
import os

from AiLearning.capabilities.requirement_model import Flow
from AiLearning.capabilities.tools import build_testcase_registry
from AiLearning.harness import read_trace, run_loop
from AiLearning.harness.tools import OUTPUTS_DIR


def _load_red_team_body() -> str:
    path = os.path.join(
        os.path.dirname(__file__), "..", "skills", "red_team", "SKILL.md"
    )
    with open(os.path.abspath(path), encoding="utf-8") as f:
        text = f.read()
    # 去掉 frontmatter，只取正文
    return text.split("---", 2)[-1].strip()


def _collect_cases(flow: Flow) -> str:
    """【降级路径】从 outputs/ 文件收集该流程已生成用例的摘要。

    优先走 run_review(cases=...) 直传；文件收集仅作 standalone 调用的兜底。
    """
    summaries: list[str] = []
    for pattern in [f"cases_{flow.id}.*.json", f"scenarios_{flow.id}.json"]:
        for path in sorted(glob.glob(os.path.join(OUTPUTS_DIR, pattern))):
            try:
                with open(path, encoding="utf-8") as f:
                    cases = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            summaries.extend(_summarize(cases))
    return "\n".join(summaries) or "（未找到已生成用例）"


def _summarize(cases: list) -> list[str]:
    """把用例 dict 列表转成「标题 ⇒ 预期」摘要行。"""
    return [
        f"- {c.get('title', '?')} ⇒ {c.get('expected', '?')}"
        for c in cases
        if isinstance(c, dict)
    ]


def build_review_prompt(flow: Flow, cases_summary: str) -> str:
    flow_text = flow.model_dump_json(indent=None)
    return f"""你是一名以挑毛病为职责的资深测试工程师（red team）。下面给你一个流程的需求结构和已生成的测试用例，你的唯一任务是找出【覆盖缺口】。

# 审查方法论（必须严格遵守其中的攻击清单与审查纪律）
{_load_red_team_body()}

# 流程需求结构（JSON）
{flow_text}

# 已生成用例（标题 ⇒ 预期结果）
{cases_summary}

# 工作流程
1. 按攻击清单六个维度逐项对照：需求结构里有的风险点，用例里有没有对应的覆盖？
2. 已覆盖的点不复述；只报告缺口，每个缺口必须指向具体 rule_id / task_id / 前置条件。
3. 调用 write_output 落盘缺口报告，文件名固定为 review_{flow.id}.json，内容为 JSON 数组（无缺口则写空数组 []）。
4. 用一两句话总结发现了几个缺口、最严重的在哪个维度，作为最终回答。"""


def run_review(flow: Flow, cases: list | None = None, max_steps: int = 6) -> dict:
    """对单个流程的已生成用例做对抗审查。返回结构与其他 capability 一致。

    cases：上游直接传入的用例 dict 列表（解耦文件命名约定）；
    None 时降级为从 outputs/ 按命名约定收集（standalone 调用兜底）。
    """
    cases_summary = (
        ("\n".join(_summarize(cases)) or "（未找到已生成用例）")
        if cases is not None
        else _collect_cases(flow)
    )
    result = run_loop(
        system_prompt=build_review_prompt(flow, cases_summary),
        task=f"请审查流程 {flow.id} {flow.name} 的用例覆盖缺口并落盘。",
        tools=build_testcase_registry(),
        max_steps=max_steps,
    )
    called_tools = [
        {"name": e["gen_ai.tool.name"], "args": e["gen_ai.tool.args"]}
        for e in read_trace(result["trace_file"])
        if e["event"] == "tool_call"
    ]
    return {
        "output": result["output"],
        "called_tools": called_tools,
        "steps": result["steps"],
        "stop_reason": result["stop_reason"],
        "trace_file": result["trace_file"],
    }
