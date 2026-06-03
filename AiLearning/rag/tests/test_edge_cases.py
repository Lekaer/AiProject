"""异常场景测试脚本。

直接调用 AiLearning/rag/ 下的各模块（不走 HTTP），测试边界和异常场景。
每个场景由对应的 case 函数自行判断行为是否符合预期。
"""
import json
import os
import sys
import tempfile
import uuid

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, BASE_DIR)

from AiLearning.rag import loader, splitter, retriever
from AiLearning.rag.generator import generate

EXISTING_COLLECTION = "col_aaf01d1195d17942"


def case1_empty_file():
    """场景1: 上传空文件 — 应抛出 ValueError 明确拒绝。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("")
        tmp_path = f.name

    try:
        loader.load_document(tmp_path)
        return False, "未抛出异常（不符合预期，空文件应被拒绝）"
    except ValueError as e:
        return True, f"ValueError: {e}"
    except Exception as e:
        return False, f"抛出了非预期的异常 {type(e).__name__}: {e}"
    finally:
        os.unlink(tmp_path)


def case2_unsupported_format():
    """场景2: 上传不支持的格式(.xlsx) — 应抛出 ValueError。"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xlsx", delete=False, encoding="utf-8") as f:
        f.write("dummy")
        tmp_path = f.name

    try:
        loader.load_document(tmp_path)
        return False, "未抛出异常（不符合预期，应拒绝 .xlsx）"
    except ValueError as e:
        return True, f"ValueError: {e}"
    except Exception as e:
        return False, f"抛出了非预期的异常 {type(e).__name__}: {e}"
    finally:
        os.unlink(tmp_path)


def case3_empty_collection():
    """场景3: 向量库为空时提问 — 检索应返回空列表，不应崩溃。"""
    empty_collection = f"test_empty_{uuid.uuid4().hex[:8]}"
    try:
        docs = retriever.retrieve("商户平台的定义是什么？", empty_collection)
        passed = len(docs) == 0
        return passed, f"检索到 {len(docs)} 篇文档"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def case4_empty_question():
    """场景4: 问题为空字符串 — 不应崩溃，可返回空结果或任意回答。"""
    try:
        docs = retriever.retrieve("", EXISTING_COLLECTION)
        answer = generate("", docs)
        passed = True  # 只要不崩溃就算通过
        return passed, f"检索到 {len(docs)} 篇文档，回答前100字: {answer[:100]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def case5_long_question():
    """场景5: 问题超长(1000字以上) — 应正常完成检索和生成。"""
    long_question = "请详细说明商户平台的概念、功能和作用。" * 50
    try:
        docs = retriever.retrieve(long_question, EXISTING_COLLECTION)
        answer = generate(long_question, docs)
        passed = len(answer) > 0
        return passed, f"问题长度={len(long_question)}字, 检索到{len(docs)}篇文档, 回答长度={len(answer)}字"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def main():
    cases = [
        ("上传空文件", "抛出 ValueError，明确拒绝空文件", case1_empty_file),
        ("上传不支持的格式(.xlsx)", "抛出 ValueError", case2_unsupported_format),
        ("向量库为空时提问", "检索返回空列表，不崩溃", case3_empty_collection),
        ("问题为空字符串", "不崩溃", case4_empty_question),
        ("问题超长(1000字以上)", "正常完成检索和生成", case5_long_question),
    ]

    results = []
    for name, expected, fn in cases:
        print(f"执行: {name}", end=" ... ")
        passed, detail = fn()
        results.append({
            "name": name,
            "expected": expected,
            "passed": passed,
            "result": detail,
        })
        print("PASS" if passed else "FAIL")

    print(f"\n{'=' * 60}")
    passed_count = sum(1 for r in results if r["passed"])
    print(f"通过: {passed_count}/{len(results)}")
    print(f"{'=' * 60}")

    for r in results:
        status = "✓" if r["passed"] else "✗"
        print(f"\n[{status}] {r['name']}")
        print(f"    预期: {r['expected']}")
        print(f"    实际: {r['result']}")

    output_path = os.path.join(os.path.dirname(__file__), "edge_case_result.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存至: {output_path}")


if __name__ == "__main__":
    main()
