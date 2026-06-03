"""LLM Judge 评估脚本。

读取 generation_result.json，调用 AI 对每条回答从忠实度、相关性、完整性三个维度打分，
汇总平均分后输出评估报告。
"""
import json
import os
import re
import sys

# 确保项目根目录在 sys.path 中，以便导入 AiLearning
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from AiLearning.service import get_client

JUDGE_PROMPT = """你是一个专业的 AI 问答质量评估员，请从以下三个维度评估答案质量：

问题：{question}
检索到的上下文：{context}
实际回答：{actual_answer}

评估维度（每项 1-5 分）：
1. 忠实度：答案是否完全基于上下文，无凭空捏造
2. 相关性：答案是否切题，没有答非所问
3. 完整性：答案是否覆盖了问题的关键点

请严格输出 JSON，不要包含任何其他文字：
{{"faithfulness": 分, "relevance": 分, "completeness": 分, "reason": "一句话说明"}}"""


def load_results(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_json(text: str) -> dict | None:
    """从 LLM 回复中提取 JSON 对象，兼容 markdown 代码块包裹。"""
    # 尝试匹配 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if m:
        text = m.group(1)
    # 尝试匹配首个 { ... } 对象
    m = re.search(r"\{[^{}]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


def judge_one(item: dict, client) -> dict | None:
    question = item["question"]
    actual_answer = item["actual_answer"]
    retrieved_docs = item.get("retrieved_docs", [])
    context = "\n\n".join(retrieved_docs) if retrieved_docs else "无相关上下文"

    prompt = JUDGE_PROMPT.format(
        question=question,
        context=context,
        actual_answer=actual_answer,
    )

    try:
        response = client.chat(messages=[{"role": "user", "content": prompt}])
        scores = extract_json(response)
        if scores is None:
            print(f"  [警告] 无法解析 LLM 输出，原始回复: {response[:200]}")
            return None
        return {
            "id": item["id"],
            "question": question,
            "expected_answer": item.get("expected_answer", ""),
            "actual_answer": actual_answer,
            **scores,
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

    # 计算平均分
    avg_faithfulness = sum(d["faithfulness"] for d in details) / len(details)
    avg_relevance = sum(d["relevance"] for d in details) / len(details)
    avg_completeness = sum(d["completeness"] for d in details) / len(details)
    avg_overall = (avg_faithfulness + avg_relevance + avg_completeness) / 3

    report = {
        "summary": {
            "total": len(details),
            "avg_faithfulness": round(avg_faithfulness, 2),
            "avg_relevance": round(avg_relevance, 2),
            "avg_completeness": round(avg_completeness, 2),
            "avg_overall": round(avg_overall, 2),
        },
        "details": details,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 50}")
    print(f"评估完成 ({len(details)}/{len(results)} 条)")
    print(f"忠实度平均分: {avg_faithfulness:.2f}")
    print(f"相关性平均分: {avg_relevance:.2f}")
    print(f"完整性平均分: {avg_completeness:.2f}")
    print(f"综合平均分:   {avg_overall:.2f}")
    print(f"{'=' * 50}")
    print(f"报告已保存至: {output_path}")


if __name__ == "__main__":
    main()
