"""缺陷知识库灌库脚本（M3-1c）。

读 data/defects/defects.jsonl → 每条记录拼 chunk 文本 → 写入 defects collection
（向量库 + BM25 索引）。schema 与设计依据见 AiLearning/docs/defect_knowledge_design.md。

纪律：
- 只灌 status=active 的记录（archived 在灌库侧排除，检索自然不可见）
- chunk 文本里现象先行（phenomenon 在最前），根因在后——匹配面是模块+现象
- 全量重建（缺陷库规模小，重建比增量简单可靠）

用法：python -m AiLearning.rag.ingest_defects
"""

import json
import os

from AiLearning.rag import bm25_store, embedder, vector_store

COLLECTION = "defects"
DATA_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "defects", "defects.jsonl"
)

REQUIRED_FIELDS = {"id", "title", "phenomenon", "service", "module", "root_cause", "dimension", "status"}


def _chunk_text(rec: dict) -> str:
    """拼检索 chunk：现象/模块在前（匹配面），根因/维度在后（负载）。"""
    return (
        f"【{rec['id']}】{rec['title']}\n"
        f"现象：{rec['phenomenon']}\n"
        f"服务/模块：{rec['service']}/{rec['module']}\n"
        f"根因：{rec['root_cause']}\n"
        f"关联维度：{rec['dimension']}"
    )


def load_records(path: str = DATA_FILE) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            missing = REQUIRED_FIELDS - rec.keys()
            if missing:
                raise ValueError(f"{path} 第 {lineno} 行缺字段: {sorted(missing)}")
            records.append(rec)
    return records


def main() -> None:
    records = [r for r in load_records() if r["status"] == "active"]
    if not records:
        print("没有 active 的缺陷记录，跳过灌库")
        return

    chunks = [_chunk_text(r) for r in records]
    embeddings = embedder.embed_texts(chunks)

    # 全量重建：先清后灌
    if vector_store.collection_exists(COLLECTION):
        vector_store.delete_collection(COLLECTION)
    vector_store.ensure_collection(COLLECTION)
    vector_store.save_documents(chunks, embeddings, COLLECTION, filename="defects.jsonl")
    bm25_store.delete_index(COLLECTION)
    bm25_store.build_index(COLLECTION, chunks)

    print(f"已灌入 {len(chunks)} 条缺陷记录到 collection '{COLLECTION}'")


if __name__ == "__main__":
    main()
