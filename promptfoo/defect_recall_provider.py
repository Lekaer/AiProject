"""promptfoo python provider：缺陷库检索评测（M3 债 1）。

纯检索不调 LLM（免费、快）：用金标准查询打 defects collection，
返回命中的 DEF id 列表，供 assertions/recall.js 判定命中率。
"""

import os
import sys

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))
except Exception:
    pass


def call_api(prompt: str, options: dict, context: dict) -> dict:
    from AiLearning.rag import retriever

    query = context.get("vars", {}).get("query") or prompt
    try:
        docs = retriever.retrieve(query, collection_name="defects", top_k=3)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

    hit_ids = [d.split("】")[0].strip("【") for d in docs if d.startswith("【")]
    return {"output": "\n".join(docs), "metadata": {"hit_ids": hit_ids}}
