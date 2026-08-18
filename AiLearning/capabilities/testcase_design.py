"""第一个 capability：测试用例设计 agent（简化版）。

与现有 AiLearning/agents/testcase_design_agent.py（多阶段 workflow，作为 fallback 保留）
是平行的两条架构：这里用通用 harness 的 agent loop，把技能规则通过 load_skill 工具
做渐进式披露（系统 prompt 只放技能目录，规则正文由模型按需加载）。

run() 返回的 called_tools 从轨迹文件收集，供轨迹断言使用。
"""

from AiLearning.harness import read_trace, run_loop
from AiLearning.capabilities.tools import build_testcase_registry
from AiLearning.skills.skill_definition import SKILL_REGISTRY


def build_system_prompt() -> str:
    """构建系统 prompt：角色 + 工具说明 + 技能目录（仅 name+description）+ 工作流程。"""
    # 渐进式披露：目录只给 name 和一句话说明，规则正文靠 load_skill 工具按需加载
    catalog_lines = [
        f"- {s.name}：{s.description}" for s in SKILL_REGISTRY.values()
    ]
    catalog = "\n".join(catalog_lines)

    return f"""你是一名资深测试工程师，负责根据需求设计高质量的测试用例。

# 可用工具
- rag_search(query)：检索测试设计知识库（历史用例、业务规则、缺陷记录）。当需求缺少业务上下文时使用。
- load_skill(name)：加载一个测试维度技能的完整规则。规则正文不在本 prompt 里，必须用这个工具按需加载；可多次调用加载多个技能。
- write_output(filename, content)：把最终用例写入 outputs/ 目录。content 必须是 JSON 数组字符串，每个元素包含 title、precondition、steps、expected 四个字段（steps 为字符串数组）。

# 技能目录（仅名称和说明，规则正文用 load_skill 加载）
{catalog}

# 技能选择（硬约束，先于一切执行）
- 大多数需求只明确涉及 1 个测试维度；只有需求明确要求覆盖多个维度时才加载多个技能。
- 需求文本若明确限定覆盖范围（如"重点覆盖 X 场景"），只加载与该限定直接对应的维度，其他维度即使能找出微弱证据也不加载。
- 只加载需求明确匹配的技能：需求里能指出具体证据（数值范围/边界字样 → boundary_value；第三方依赖、异常、故障 → exception_path；角色/权限 → permission_security；状态流转 → state_machine；事务/重复提交/缓存 → data_consistency；多模块组合 → combinatorial）。没有明确证据的维度一律不加载。
- 严禁"以防万一"加载可能沾边的技能：加载不匹配的技能会稀释生成焦点、浪费上下文，是明确禁止的行为。
- 每个技能最多加载一次，不要重复加载。
- 调用 load_skill 之前，先用一句话说明你判断出的维度及对应证据，再按此调用工具。

# 工作流程（必须遵守）
1. 先理解需求，判断需求明确涉及哪些测试维度（对照上面"技能选择"的证据标准），拿不准的维度不要加载。
2. 若需求涉及具体业务背景且你不确定细节，可先用 rag_search 补充上下文；不需要时可跳过。
3. 只对判断出的维度调用 load_skill 加载对应技能（每个最多一次）。
4. 严格按照加载到的技能规则设计测试用例。
5. 调用 write_output 把用例落盘为 JSON 数组。每个用例字段：title（用例标题）、precondition（前置条件）、steps（步骤数组）、expected（预期结果）。
6. 最后用一两句话总结你做了什么，作为最终回答结束任务。

# 约束
- 必须通过 load_skill 加载技能规则后再设计用例，不允许凭经验直接设计。
- 最终产物必须通过 write_output 落盘，不要只在回答里列出用例。
- 用例数量聚焦质量而非数量，每个维度 2-5 条即可。"""


def run(requirement: str, max_steps: int = 10) -> dict:
    """用 harness 的 loop 跑一个简化版用例设计任务。

    Returns:
        {
            "output": 最终回答文本,
            "called_tools": [{"name": ..., "args": {...}}]，从轨迹收集,
            "steps": LLM 轮数,
            "stop_reason": "final" | "max_steps" | "error",
            "trace_file": 轨迹文件路径,
        }
    """
    result = run_loop(
        system_prompt=build_system_prompt(),
        task=f"请为以下需求设计测试用例：\n\n{requirement}",
        tools=build_testcase_registry(),
        max_steps=max_steps,
    )
    # 从轨迹收集工具调用序列（轨迹断言要用这个结构）
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
