"""LLM Judge 评估脚本（二元检查表版）。

读取 generation_result.json，调用 AI 对每条回答从 3 个维度、6 项二元条件评估，
汇总 pass_rate 后输出评估报告。

改进：从 1-5 数值量表改为 F1/F2, R1/R2, C1/C2 六项二元检查表。
  每项 pass/fail，维度 pass = 子条件全部通过。
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from AiLearning.service import get_client

JUDGE_PROMPT = """你是一个专业的 AI 问答质量评估员。对以下问答结果逐条判断。

问题：{question}
预期答案：{expected_answer}
实际回答：{actual_answer}
检索到的上下文：{context}

判断以下每条是否成立（输出 true 或 false），严格只输出 JSON：

忠实度检查：
  F1: 回答中的所有事实性陈述都可以在「检索到的上下文」中找到原文支持
  F2: 回答没有凭空添加上下文未提及的功能、数字、人名、日期

相关性检查：
  R1: 回答直接回应了问题，没有答非所问
  R2: 回答的主体内容与问题相关，没有大量偏离主题的无关信息

完整性检查：
  C1: 回答覆盖了「预期答案」中列出的所有关键要点
  C2: 如果问题是复合问题，回答对所有子问题都给出了回应

输出格式（只输出 JSON，不要 markdown 包裹）：
{{
  "F1": true/false, "F2": true/false, "faithfulness_pass": true/false,
  "R1": true/false, "R2": true/false, "relevance_pass": true/false,
  "C1": true/false, "C2": true/false, "completeness_pass": true/false,
  "summary": "一句话说明主要问题（如无问题则说 无）"
}}"""


def load_results(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_json(text: str) -> dict | None:
    """从 LLM 回复中提取 JSON 对象，兼容 markdown 代码块包裹。"""
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1)
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def judge_one(item: dict, client) -> dict | None:
    question = item["question"]
    actual_answer = item["actual_answer"]
    expected = item.get("expected_answer", "")
    retrieved_docs = item.get("retrieved_docs", [])
    context = "\n\n".join(retrieved_docs) if retrieved_docs else "无相关上下文"

    prompt = JUDGE_PROMPT.format(
        question=question,
        expected_answer=expected,
        actual_answer=actual_answer,
        context=context,
    )

    try:
        response = client.chat(messages=[{"role": "user", "content": prompt}])
        scores = extract_json(response)
        if scores is None:
            print(f"  [警告] 无法解析 LLM 输出，原始回复: {response[:200]}")
            return None

        # 读取各个布尔字段，兼容缺失字段（默认 false）
        f1 = scores.get("F1", False)
        f2 = scores.get("F2", False)
        r1 = scores.get("R1", False)
        r2 = scores.get("R2", False)
        c1 = scores.get("C1", False)
        c2 = scores.get("C2", False)

        # LLM 可能返回 "true" 字符串或布尔值
        def _to_bool(v):
            if isinstance(v, bool):
                return v
            if isinstance(v, str):
                return v.strip().lower() == "true"
            return False

        f1, f2 = _to_bool(f1), _to_bool(f2)
        r1, r2 = _to_bool(r1), _to_bool(r2)
        c1, c2 = _to_bool(c1), _to_bool(c2)

        faithfulness_pass = f1 and f2
        relevance_pass = r1 and r2
        completeness_pass = c1 and c2

        return {
            "id": item["id"],
            "question": question,
            "expected_answer": expected,
            "actual_answer": actual_answer,
            "faithfulness": {"F1": f1, "F2": f2, "pass": faithfulness_pass},
            "relevance": {"R1": r1, "R2": r2, "pass": relevance_pass},
            "completeness": {"C1": c1, "C2": c2, "pass": completeness_pass},
            "overall_pass": faithfulness_pass and relevance_pass and completeness_pass,
            "summary": scores.get("summary", ""),
        }
    except Exception as e:
        print(f"  [错误] {e}")
        return None


def main():
    input_path = os.path.join(
        os.path.dirname(__file__), "AiLearning", "rag", "tests", "generation_result.json"
    )
    output_path = os.path.join(
        os.path.dirname(__file__), "AiLearning", "rag", "tests", "judge_result.json"
    )

    results = load_results(input_path)
    print(f"加载生成结果：{len(results)} 条数据")

    client = get_client()

    details = []
    for i, item in enumerate(results, 1):
        print(f"[{i}/{len(results)}] 评估: {item['question']}")
        judged = judge_one(item, client)
        if judged:
            details.append(judged)

    if not details:
        print("没有成功评估的记录")
        return

    # ── 统计各项 pass_rate ──
    total = len(details)
    faith_pass_count = sum(1 for d in details if d["faithfulness"]["pass"])
    relev_pass_count = sum(1 for d in details if d["relevance"]["pass"])
    compl_pass_count = sum(1 for d in details if d["completeness"]["pass"])
    overall_pass_count = sum(1 for d in details if d["overall_pass"])

    # 每个子条件的通过率
    f1_pass = sum(1 for d in details if d["faithfulness"]["F1"]) / total
    f2_pass = sum(1 for d in details if d["faithfulness"]["F2"]) / total
    r1_pass = sum(1 for d in details if d["relevance"]["R1"]) / total
    r2_pass = sum(1 for d in details if d["relevance"]["R2"]) / total
    c1_pass = sum(1 for d in details if d["completeness"]["C1"]) / total
    c2_pass = sum(1 for d in details if d["completeness"]["C2"]) / total

    report = {
        "summary": {
            "total": total,
            "faithfulness_pass_rate": round(faith_pass_count / total, 2),
            "relevance_pass_rate": round(relev_pass_count / total, 2),
            "completeness_pass_rate": round(compl_pass_count / total, 2),
            "overall_pass_rate": round(overall_pass_count / total, 2),
            "condition_details": {
                "F1_factual_support": round(f1_pass, 2),
                "F2_no_hallucination": round(f2_pass, 2),
                "R1_direct_answer": round(r1_pass, 2),
                "R2_no_drift": round(r2_pass, 2),
                "C1_key_points_covered": round(c1_pass, 2),
                "C2_sub_questions_answered": round(c2_pass, 2),
            },
        },
        "details": details,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 50}")
    print(f"评估完成 ({total} 条)")
    print(f"忠实度通过率:   {faith_pass_count}/{total} ({faith_pass_count / total:.0%})  "
          f"[F1={f1_pass:.0%} F2={f2_pass:.0%}]")
    print(f"相关性通过率:   {relev_pass_count}/{total} ({relev_pass_count / total:.0%})  "
          f"[R1={r1_pass:.0%} R2={r2_pass:.0%}]")
    print(f"完整性通过率:   {compl_pass_count}/{total} ({compl_pass_count / total:.0%})  "
          f"[C1={c1_pass:.0%} C2={c2_pass:.0%}]")
    print(f"综合通过率:     {overall_pass_count}/{total} ({overall_pass_count / total:.0%})")
    print(f"{'=' * 50}")
    print(f"报告已保存至: {output_path}")


if __name__ == "__main__":
    main()
