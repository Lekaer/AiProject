"""任务级用例生成（M2-3）：维度选择从"整篇需求"收窄到"单个任务"。

与 M1 的 run()（整段需求文本，全局选维度，保留作对比/fallback）平行：
本模块的 run_for_task() 以需求模型中的单个 Task 为作用域，
证据（任务类型 + 任务描述 + 规则列表）直接写进 prompt，
模型仍通过 load_skill 渐进式披露加载维度规则——节点级维度选择由此实现。

可追溯约定：生成的每条点用例必须带 rule_ids 字段（引用的 Rule.id 列表），
覆盖率统计以此为准（pipeline 从 write_output 的参数里收集）。
"""

from AiLearning.capabilities.requirement_model import Flow, Task
from AiLearning.capabilities.tools import build_testcase_registry
from AiLearning.harness import read_trace, run_loop
from AiLearning.skills.skill_definition import SKILL_REGISTRY


def build_task_prompt(flow: Flow, task: Task, defect_context: str = "") -> str:
    """任务级系统 prompt：角色 + 工具说明 + 技能目录 + 本任务的作用域信息。

    defect_context：管线检索到的相关历史缺陷文本（M3-1，可能为空串）。
    """
    catalog = "\n".join(f"- {s.name}：{s.description}" for s in SKILL_REGISTRY.values())

    rules_text = "\n".join(
        f"  - {r.id}：当 {r.condition} 时，应 {r.expected}"
        + ("（此条为推断信息，未经文档确认）" if r.assumed else "")
        + (f"（变更标记：{r.change}）" if r.change != "new" else "")
        for r in task.rules
    ) or "  （本任务无明确规则，基于任务描述设计）"

    change_note = f"- 变更标记：{task.change}（modified/unchanged_affected 表示这是优化类需求，回归维度是候选证据）\n" if task.change != "new" else ""

    defect_section = f"""
# 历史缺陷（本任务相关，优先参考）
以下是从缺陷库检索到的、与本任务相关的历史问题。缺陷的"关联维度"可作为维度选择的直接证据；缺陷描述的失效场景应优先转化为测试点。
{defect_context}
""" if defect_context else ""

    return f"""你是一名资深测试工程师，负责为需求中的【单个任务】设计高质量的测试用例（点用例）。

# 任务上下文
- 所属流程：{flow.id} {flow.name}（前置条件：{"；".join(flow.preconditions) or "无"}）
- 当前任务：{task.id} {task.name}（类型：{task.type}）
- 任务说明：{task.description}
- 提交场景：{"；".join(task.scenarios) or "未说明"}
- 数据依赖：{"；".join(task.data_dependencies) or "未说明"}
{change_note}- 任务规则（用例必须引用规则 ID）：
{rules_text}
{defect_section}
# 可用工具
- rag_search(query)：检索测试设计知识库。当任务缺少业务上下文时使用。
- load_skill(name)：加载一个测试维度技能的完整规则。规则正文不在本 prompt 里，必须用这个工具按需加载。
- write_output(filename, content)：把用例写入 outputs/ 目录。content 是 JSON 数组字符串，每个元素包含 title、precondition、steps（字符串数组）、expected、rule_ids（字符串数组，本用例覆盖的规则 ID，无对应规则时为空数组）五个字段。

# 技能目录（仅名称和说明，规则正文用 load_skill 加载）
{catalog}

# 技能选择（硬约束，先于一切执行）
- 大多数任务只明确涉及 1 个测试维度；只有任务信息明确要求覆盖多个维度时才加载多个技能（最多 2 个）。
- 只加载本任务明确匹配的维度：证据必须来自上面的任务信息（任务类型/描述/规则/变更标记）。例如：同步类任务、外部接口 → data_consistency 或 exception_path；数值范围 → boundary_value；状态变化 → state_machine；角色权限 → permission_security；change 为 modified/unchanged_affected → regression。
- 没有明确证据的维度一律不加载；严禁"以防万一"加载。
- 每个技能最多加载一次；调用 load_skill 前先用一句话说明判断出的维度及证据。

# 工作流程
1. 理解任务上下文，按证据标准判断维度。
2. 必要时用 rag_search 补业务上下文。
3. 只对判断出的维度调用 load_skill。
4. 严格按加载到的技能规则，围绕本任务的规则和场景设计点用例（每个维度 2-5 条）。
5. 调用 write_output 落盘，文件名固定为 cases_{task.id}.json。
6. 用一两句话总结作为最终回答。"""


def run_for_task(flow: Flow, task: Task, max_steps: int = 10, defect_context: str = "") -> dict:
    """为需求模型中的单个任务生成点用例。返回结构与 testcase_design.run() 一致。

    defect_context：pipeline 检索到的相关历史缺陷文本（M3-1），空串表示无命中。
    """
    result = run_loop(
        system_prompt=build_task_prompt(flow, task, defect_context),
        task=f"请为任务 {task.id} {task.name} 设计点用例并落盘。",
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
