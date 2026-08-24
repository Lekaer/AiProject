"""用例生成管线：文档 → 需求模型 → 点用例 + 场景用例 → 对抗审查 → 缺口修复。

run_document() 端到端入口：
1. parse_requirement 把 PRD 解析为需求模型（map-reduce 的 map 前置）
2. 逐任务生成点用例（节点级维度选择 + 缺陷库注入）
3. 逐流程生成场景用例（主干 + 单点变异）
4. 对抗审查找覆盖缺口（用例直传，不依赖文件命名约定）
5. 缺口修复：按缺口生成补充用例（evaluator-optimizer 单轮闭环）
6. 从各 loop 的 write_output 参数中收集 rule_ids，计算规则覆盖率

task_limit 用于控制成本（冒烟时只跑前 N 个任务），正式跑传 None。
"""

import json

from AiLearning.capabilities import scenario_design, task_case_design
from AiLearning.capabilities.requirement_model import Flow, RequirementModel, Task
from AiLearning.capabilities.requirement_parse import parse_requirement, ParseError


def _retrieve_defects(flow: Flow, task: Task, top_k: int = 3) -> str:
    """M3-1：用任务结构化字段程序构造查询，检索缺陷库（确定性步骤，不靠模型选词）。

    检索不可用（索引未建/embedding 失败）时优雅降级为空串——生成照常进行。
    """
    query = " ".join([
        flow.name, task.name, task.type, *task.data_dependencies,
    ])
    try:
        from AiLearning.rag import retriever

        docs = retriever.retrieve(query, collection_name="defects", top_k=top_k)
    except Exception:
        return ""
    return "\n\n---\n\n".join(docs)


def _collect_cases(called_tools: list[dict]) -> list[dict]:
    """从一次 loop 的工具调用里提取 write_output 写入的用例 dict 列表。"""
    cases: list[dict] = []
    for call in called_tools:
        if call["name"] != "write_output":
            continue
        try:
            parsed = json.loads(call["args"].get("content", "[]"))
        except (json.JSONDecodeError, TypeError):
            continue
        cases.extend(c for c in parsed if isinstance(c, dict))
    return cases


def _collect_rule_ids(called_tools: list[dict]) -> set[str]:
    """从一次 loop 的工具调用里提取 write_output 写入内容的 rule_ids。"""
    ids: set[str] = set()
    for case in _collect_cases(called_tools):
        ids.update(case.get("rule_ids") or [])
    return ids


def _extract_gaps(review_result: dict) -> list[dict]:
    """从审查结果里解析缺口报告（write_output 写入的 JSON 数组）。"""
    for call in review_result.get("called_tools", []):
        if call["name"] != "write_output":
            continue
        try:
            gaps = json.loads(call["args"].get("content", "[]"))
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(gaps, list):
            return [g for g in gaps if isinstance(g, dict)]
    return []


def run_document(
    source: str,
    task_limit: int | None = None,
    model: RequirementModel | None = None,
) -> dict:
    """端到端跑一篇需求文档。model 已解析好时可直接传入（跳过重复解析）。

    Returns:
        {
            "requirement": 需求模型统计（RequirementModel.stats()）,
            "open_questions": [...],
            "task_results": {task_id: run_for_task 返回},
            "scenario_results": {flow_id: run_for_flow 返回},
            "coverage": {"covered": 已覆盖规则数, "total": 规则总数, "ratio": 覆盖率},
        }
    """
    if model is None:
        try:
            model = parse_requirement(source)
        except ParseError as e:
            return {
                "requirement": None,
                "error": f"需求解析失败：{e}",
                "open_questions": [],
                "task_results": None,
                "scenario_results": None,
                "review_results": None,
                "coverage": None
            }

    task_results: dict[str, dict] = {}
    covered_rule_ids: set[str] = set()
    all_rule_ids = {
        r.id for r in model.all_rules
    }

    remaining = task_limit
    for flow in model.flows:
        for task in flow.tasks:
            if remaining is not None and remaining <= 0:
                break
            defect_context = _retrieve_defects(flow, task)
            task_results[task.id] = task_case_design.run_for_task(
                flow, task, defect_context=defect_context
            )
            task_results[task.id]["defect_hits"] = defect_context.count("【DEF-")
            covered_rule_ids |= _collect_rule_ids(task_results[task.id]["called_tools"])
            if remaining is not None:
                remaining -= 1

    scenario_results: dict[str, dict] = {}
    for flow in model.flows:
        if not flow.tasks:
            continue
        scenario_results[flow.id] = scenario_design.run_for_flow(flow)

    # M3-2/M3 债 2+3：对抗审查（cases 直传解耦）→ 缺口修复闭环
    from AiLearning.capabilities import adversarial_review, gapfix_design

    review_results: dict[str, dict] = {}
    gapfix_results: dict[str, dict] = {}
    for flow in model.flows:
        if not flow.tasks:
            continue
        # 直传该流程已生成的用例（点用例 + 场景用例），不依赖文件命名约定
        flow_cases: list[dict] = []
        for task in flow.tasks:
            if task.id in task_results:
                flow_cases.extend(_collect_cases(task_results[task.id]["called_tools"]))
        if flow.id in scenario_results:
            flow_cases.extend(_collect_cases(scenario_results[flow.id]["called_tools"]))

        review_results[flow.id] = adversarial_review.run_review(flow, cases=flow_cases)

        # 闭环：审查发现的缺口 → 生成补充用例（gaps 为空则跳过，不花 LLM 调用）
        gaps = _extract_gaps(review_results[flow.id])
        review_results[flow.id]["gap_count"] = len(gaps)
        gapfix = gapfix_design.run_gapfix(flow, gaps)
        if gapfix is not None:
            gapfix_results[flow.id] = gapfix
            covered_rule_ids |= _collect_rule_ids(gapfix["called_tools"])

    covered_in_scope = covered_rule_ids & all_rule_ids
    return {
        "requirement": model.stats(),
        "open_questions": model.open_questions,
        "task_results": task_results,
        "scenario_results": scenario_results,
        "review_results": review_results,
        "gapfix_results": gapfix_results,
        "coverage": {
            "covered": len(covered_in_scope),
            "total": len(all_rule_ids),
            "ratio": round(len(covered_in_scope) / len(all_rule_ids), 3) if all_rule_ids else None,
        },
    }
