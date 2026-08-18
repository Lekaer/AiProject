"""缺口修复生成（M3 债 2）：对抗审查 → 再生成的闭环。

对抗审查产出的缺口报告（review_<flow>.json）不再只是终点：
本模块把缺口作为输入，生成补充用例堵住缺口，完成
"生成 → 审查 → 补漏"的 evaluator-optimizer 闭环（一轮）。

设计要点：
- 缺口必须指向具体 rule_id/task_id（red_team 审查纪律保证），修复生成按图索骥
- 补充用例带 rule_ids，覆盖率统计自动纳入
- 每轮只修一次（不循环迭代）——多轮迭代留给后续，先验证单轮价值
"""

from AiLearning.capabilities.requirement_model import Flow
from AiLearning.capabilities.tools import build_testcase_registry
from AiLearning.harness import read_trace, run_loop


def build_gapfix_prompt(flow: Flow, gaps: list[dict]) -> str:
    gap_text = "\n".join(
        f"- [{g.get('gap_type', '?')}] {g.get('target_id', '?')}：{g.get('description', '')}"
        f"（建议：{g.get('suggested_case', '无')}）"
        for g in gaps
    )
    flow_text = flow.model_dump_json(indent=None)

    return f"""你是一名资深测试工程师。同事对一个流程的测试用例做了对抗审查，发现了若干覆盖缺口。你的任务是：只为这些缺口生成补充用例。

# 流程需求结构（JSON）
{flow_text}

# 审查发现的缺口（每个缺口已定位到具体规则/任务）
{gap_text}

# 可用工具
- load_skill(name)：加载测试维度技能的完整规则。根据缺口类型选择（边界→boundary_value，异常→exception_path，权限→permission_security，状态→state_machine，一致性→data_consistency）。
- write_output(filename, content)：落盘 JSON 数组，每个元素含 title、precondition、steps（字符串数组）、expected、rule_ids（字符串数组）五个字段。

# 要求（硬约束）
1. 只为列出的缺口生成用例，一个缺口至少一条；不要重新生成已被覆盖的内容。
2. 每条用例必须能映射回缺口指向的 rule_id / task_id（写进 rule_ids）。
3. 先按缺口类型调用 load_skill 加载对应维度规则，再按其规则展开用例。
4. 调用 write_output 落盘，文件名固定为 gapfix_{flow.id}.json。
5. 用一两句话总结作为最终回答。"""


def run_gapfix(flow: Flow, gaps: list[dict], max_steps: int = 8) -> dict | None:
    """对审查发现的缺口生成补充用例。gaps 为空时返回 None（不消耗 LLM 调用）。"""
    if not gaps:
        return None
    result = run_loop(
        system_prompt=build_gapfix_prompt(flow, gaps),
        task=f"请为流程 {flow.id} 的 {len(gaps)} 个覆盖缺口生成补充用例并落盘。",
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
