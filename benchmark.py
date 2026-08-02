"""端到端性能 benchmark：业务建模 → Skill 选择 → 测试点生成 → 用例展开。

使用固定测试文档和问题，输出各阶段耗时和 token 用量报告。
可选：BENCHMARK_ASSERT=1 时对总耗时做阈值断言（适用于 CI）。

用法：
    python benchmark.py              # 仅输出报告
    BENCHMARK_ASSERT=1 python benchmark.py  # 输出报告 + 阈值断言
"""

import json
import logging
import os
import time

from AiLearning.agents.modeling_agent import ModelingAgent
from AiLearning.agents.testcase_design_agent import TestCaseDesignAgent
from AiLearning.rag.loader import load_document
from AiLearning.skills import ModelingContext

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("benchmark")

# ── benchmark 固定输入 ─────────────────────────────────────────────
BENCHMARK_DOC = "AiLearning/docs/新商户平台概念文字版.pdf"
BENCHMARK_QUESTION = "为新商户入驻流程设计测试用例"

# ── 阈值（CI 断言用）───────────────────────────────────────────────
P95_TOTAL_SECONDS = float(os.environ.get("BENCHMARK_TOTAL_S", "120"))
P95_MODELING_SECONDS = float(os.environ.get("BENCHMARK_MODELING_S", "60"))
P95_DESIGN_SECONDS = float(os.environ.get("BENCHMARK_DESIGN_S", "90"))


def load_document_text(path: str) -> str:
    """加载文档并拼接为全文。"""
    docs = load_document(path)
    return "\n\n".join(d.page_content for d in docs)


def main():
    assert os.path.exists(BENCHMARK_DOC), f"benchmark 文档不存在: {BENCHMARK_DOC}"
    do_assert = os.environ.get("BENCHMARK_ASSERT", "") == "1"

    logger.info("=== benchmark 开始 ===")
    logger.info("文档: %s", BENCHMARK_DOC)
    logger.info("问题: %s", BENCHMARK_QUESTION)

    # ── 加载文档 ──
    t_total = time.perf_counter()
    doc_text = load_document_text(BENCHMARK_DOC)
    load_elapsed = round((time.perf_counter() - t_total) * 1000)
    logger.info("文档加载完成 chars=%d elapsed=%dms", len(doc_text), load_elapsed)

    # ── Phase A: 业务建模 ──
    logger.info("--- Phase A: 业务建模 ---")
    t_modeling = time.perf_counter()
    modeler = ModelingAgent()
    model = modeler.build_model([doc_text])
    modeling_elapsed = round((time.perf_counter() - t_modeling) * 1000)
    model_summary = {
        "domain_type": model.get("domain_type"),
        "entities": len(model.get("entities", [])),
        "flows": len(model.get("flows", [])),
        "states": len(model.get("states", [])),
        "rules": len(model.get("rules", [])),
    }
    logger.info("业务建模完成 %s elapsed=%dms", model_summary, modeling_elapsed)

    # ── Phase B: 测试用例设计 ──
    logger.info("--- Phase B: 测试用例设计 ---")
    t_design = time.perf_counter()
    designer = TestCaseDesignAgent()
    result = designer.execute(
        BENCHMARK_QUESTION,
        requirement_doc=doc_text,
        modeling=ModelingContext(enabled=True, previous_model=model),
    )
    design_elapsed = round((time.perf_counter() - t_design) * 1000)

    cases = json.loads(result.answer) if result.answer else []
    metadata = result.metadata
    logger.info(
        "用例设计完成 skills=%s points=%d cases=%d elapsed=%dms",
        metadata.get("selected_skills", []),
        metadata.get("test_points_count", 0),
        len(cases),
        design_elapsed,
    )

    # ── 汇总 ──
    total_elapsed = round((time.perf_counter() - t_total) * 1000)

    report = {
        "benchmark": {
            "doc": BENCHMARK_DOC,
            "question": BENCHMARK_QUESTION,
        },
        "timing_ms": {
            "load": load_elapsed,
            "modeling": modeling_elapsed,
            "design": design_elapsed,
            "total": total_elapsed,
        },
        "modeling_summary": model_summary,
        "design_summary": {
            "selected_skills": metadata.get("selected_skills", []),
            "test_points": metadata.get("test_points_count", 0),
            "test_cases": len(cases),
            "impact_analysis": metadata.get("impact_analysis"),
        },
    }

    print("\n" + "=" * 60)
    print("Benchmark Report")
    print("=" * 60)
    print(json.dumps(report, ensure_ascii=False, indent=2))

    # ── 阈值断言 ──
    if do_assert:
        total_s = total_elapsed / 1000
        modeling_s = modeling_elapsed / 1000
        design_s = design_elapsed / 1000
        failures = []

        if total_s > P95_TOTAL_SECONDS:
            failures.append(f"总耗时 {total_s:.1f}s > {P95_TOTAL_SECONDS}s")
        if modeling_s > P95_MODELING_SECONDS:
            failures.append(f"建模耗时 {modeling_s:.1f}s > {P95_MODELING_SECONDS}s")
        if design_s > P95_DESIGN_SECONDS:
            failures.append(f"设计耗时 {design_s:.1f}s > {P95_DESIGN_SECONDS}s")

        if failures:
            msg = "BENCHMARK ASSERT FAILED:\n" + "\n".join(f"  - {f}" for f in failures)
            logger.error(msg)
            raise SystemExit(msg)
        else:
            logger.info("BENCHMARK ASSERT PASSED (all within thresholds)")

    logger.info("=== benchmark 完成 ===")


if __name__ == "__main__":
    main()
