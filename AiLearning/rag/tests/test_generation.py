"""批量问答评估脚本。

读取评估集，对每条问题依次执行检索 + 生成，将问答结果输出为 JSON。
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, BASE_DIR)

from AiLearning.rag import retriever
from AiLearning.rag.generator import generate


def load_eval_set(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_generation(eval_set: list[dict], collection_name: str) -> list[dict]:
    results = []

    for i, item in enumerate(eval_set, 1):
        question = item["question"]
        expected_answer = item["expected_answer"]

        retrieved_docs = retriever.retrieve(question, collection_name)
        actual_answer = generate(question, retrieved_docs)

        results.append({
            "id": i,
            "question": question,
            "expected_answer": expected_answer,
            "actual_answer": actual_answer,
            "retrieved_docs": retrieved_docs,
        })

        print(f"[{i}/{len(eval_set)}] 已完成: {question}")

    return results


def main():
    eval_path = os.path.join(os.path.dirname(__file__), "eval_set.json")
    output_path = os.path.join(os.path.dirname(__file__), "generation_result.json")

    collection_name = sys.argv[1] if len(sys.argv) > 1 else "col_aaf01d1195d17942"

    eval_set = load_eval_set(eval_path)
    print(f"加载评估集：{len(eval_set)} 条数据")
    print(f"检索集合：{collection_name}")

    results = run_generation(eval_set, collection_name)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存至: {output_path}")


if __name__ == "__main__":
    main()
