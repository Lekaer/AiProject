"""检索质量评估脚本。

读取评估集，对每条问题调用 retriever.retrieve() 检索 top_k=3 篇文档，
判断检索结果中是否包含 answer_keywords 中的任意关键词（Hit），
统计整体 Hit Rate 并输出结果。
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, BASE_DIR)

from AiLearning.rag import retriever


def load_eval_set(path: str) -> list[dict]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_hit(texts: list[str], keywords: list[str]) -> bool:
    """检索结果中是否包含任意关键词。"""
    for keyword in keywords:
        for text in texts:
            if keyword in text:
                return True
    return False


def evaluate(eval_set: list[dict], collection_name: str, top_k: int = 3) -> dict:
    results = []
    hits = 0
    missed = []

    for item in eval_set:
        question = item["question"]
        keywords = item["answer_keywords"]

        retrieved = retriever.retrieve(question, collection_name, top_k=top_k)
        is_hit = check_hit(retrieved, keywords)

        results.append({
            "question": question,
            "expected_answer": item["expected_answer"],
            "answer_keywords": keywords,
            "type": item["type"],
            "retrieved_docs": retrieved,
            "hit": is_hit,
        })

        if is_hit:
            hits += 1
        else:
            missed.append(question)

    hit_rate = hits / len(eval_set) if eval_set else 0
    return {
        "collection": collection_name,
        "top_k": top_k,
        "total": len(eval_set),
        "hits": hits,
        "hit_rate": round(hit_rate, 4),
        "missed_questions": missed,
        "details": results,
    }


def main():
    eval_path = os.path.join(os.path.dirname(__file__), "eval_set.json")
    output_path = os.path.join(os.path.dirname(__file__), "retrieval_result.json")

    collection_name = sys.argv[1] if len(sys.argv) > 1 else "col_aaf01d1195d17942"
    print(collection_name)
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 3

    eval_set = load_eval_set(eval_path)
    print(f"加载评估集：{len(eval_set)} 条数据")
    print(f"检索集合：{collection_name}，top_k={top_k}")

    summary = evaluate(eval_set, collection_name, top_k)

    print(f"\n{'=' * 60}")
    print(f"整体 Hit Rate: {summary['hit_rate']:.2%} ({summary['hits']}/{summary['total']})")
    print(f"{'=' * 60}")

    print("\n各问题检索结果：")
    for i, detail in enumerate(summary["details"], 1):
        status = "✓ HIT" if detail["hit"] else "✗ MISS"
        print(f"\n[{i}] [{status}] {detail['type']}: {detail['question']}")
        print(f"    关键词: {detail['answer_keywords']}")
        print(f"    检索结果 ({len(detail['retrieved_docs'])} docs):")
        for j, doc in enumerate(detail["retrieved_docs"], 1):
            preview = doc[:150] + "..." if len(doc) > 150 else doc
            print(f"      [{j}] {preview}")

    if summary["missed_questions"]:
        print(f"\n{'=' * 60}")
        print(f"未命中问题列表 ({len(summary['missed_questions'])}):")
        for q in summary["missed_questions"]:
            print(f"  - {q}")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存至: {output_path}")


if __name__ == "__main__":
    main()
