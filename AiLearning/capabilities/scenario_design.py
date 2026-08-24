"""场景用例生成（M2-3）：按流程结构把任务节点串成连贯路径。

与点用例（task_case_design，管规则正确性）互补：场景用例管流程正确性
（状态流转、跨节点数据传递、前置条件）。

串联依据：Flow.preconditions + Task.relations（sequence/depends_on/mutex）
+ Task.produces（A 的产出 = B 的前置）。
组合控制：主干正常流 1 条 + 每个分叉/异常分支 1 条单点变异，不做全排列。
"""

from AiLearning.capabilities.requirement_model import Flow
from AiLearning.capabilities.tools import build_testcase_registry
from AiLearning.harness import read_trace, run_loop


def build_scenario_prompt(flow: Flow) -> str:
    """场景生成 prompt：给出流程的完整结构，要求输出主干 + 单点变异路径。"""
    tasks_text = "\n".join(
        f"  - {t.id} {t.name}（类型 {t.type}）：{t.description}\n"
        f"    产出：{'；'.join(t.produces) or '未说明'}\n"
        f"    关系：{'；'.join(f'{r.type}→{r.target}' for r in t.relations) or '无'}"
        for t in flow.tasks
    )

    return f"""你是一名资深测试工程师，负责为业务流程设计【场景用例】——把流程中的任务节点串成连贯的端到端路径。

# 流程结构
- 流程：{flow.id} {flow.name}（{flow.description}）
- 前置条件：{"；".join(flow.preconditions) or "无"}
- 流程间关系：{"；".join(f'{r.type}→{r.target}' for r in flow.relations) or "无"}
- 任务节点：
{tasks_text}

# 可用工具
- write_output(filename, content)：把用例写入 outputs/ 目录。content 是 JSON 数组字符串，每个元素包含 title、precondition、steps（字符串数组，每步注明对应的任务 ID）、expected、task_ids（字符串数组，本场景覆盖的任务 ID）五个字段。

# 设计要求（硬约束）
1. 先设计 1 条【主干场景】：覆盖流程主路径（最常见的正常流转），贯穿尽可能多的任务节点。
2. 再设计若干条【变异场景】：每条只改变一个点（单点变异）——某个前置条件不满足、某个任务走了异常分支、某个任务间的数据传递出错。禁止全排列组合。
3. 场景数量 = 1 条主干 + 每个主要分叉 1 条，总数不超过 {max(len(flow.tasks), 3)} 条。
4. 每条场景的 steps 必须连贯：前一步的产出是后一步的输入（参考各任务的"产出"）。
5. 调用 write_output 落盘，文件名固定为 scenarios_{flow.id}.json。
6. 用一两句话总结作为最终回答。"""


def run_for_flow(flow: Flow, max_steps: int = 8) -> dict:
    """为需求模型中的单个流程生成场景用例。返回结构与 testcase_design.run() 一致。"""
    result = run_loop(
        system_prompt=build_scenario_prompt(flow),
        task=f"请为流程 {flow.id} {flow.name} 设计场景用例并落盘。",
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
