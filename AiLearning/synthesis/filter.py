"""数据合成过滤器：LLM 质量评分 + 去重 + 过滤 + 结构校验。"""

import json
import logging
import os

from AiLearning.prompts.synthesis import DEFAULT_QUALITY_SCORING_PROMPT
from AiLearning.service import get_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _parse_json_list(raw: str) -> list:
    """3 级 fallback JSON 数组解析。"""
    import re

    text = raw.strip()
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    logger.warning("无法解析 LLM 评分响应: %s", text[:300])
    return []


# ── 质量评分 ─────────────────────────────────────────────────

def score_quality(
    client,
    samples: list[dict],
    batch_size: int = 20,
) -> list[dict]:
    """LLM-as-Judge 批量评分。

    每批最多 20 条，减少单次 LLM 调用 token 消耗。
    返回带 _score 字段的样本列表。
    """
    scored: list[dict] = []
    total_batches = (len(samples) + batch_size - 1) // batch_size

    for batch_idx in range(0, len(samples), batch_size):
        batch = samples[batch_idx : batch_idx + batch_size]
        batch_num = batch_idx // batch_size + 1
        logger.info("评分批次 %d/%d: %d 条", batch_num, total_batches, len(batch))

        # 构建评分输入：只发需求 + 用例摘要，减少 token
        simplified = []
        for j, s in enumerate(batch):
            cases = s.get("cases", [])
            simplified.append({
                "index": j,
                "requirement": s.get("requirement_doc", "")[:400],
                "case_summary": {
                    "count": len(cases),
                    "sample_titles": [c.get("title", "") for c in cases[:3]],
                },
            })

        prompt = DEFAULT_QUALITY_SCORING_PROMPT.format(
            samples_json=json.dumps(simplified, ensure_ascii=False)
        )

        try:
            response = client.chat(
                messages=[
                    {"role": "system", "content": DEFAULT_QUALITY_SCORING_PROMPT.system},
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
                max_tokens=8192,
            )
            scores = _parse_json_list(response)

            for s in scores:
                idx = s.get("index", -1)
                if 0 <= idx < len(batch):
                    entry = batch[idx]
                    entry["_score"] = {
                        "faithfulness": s.get("faithfulness", 1),
                        "completeness": s.get("completeness", 1),
                        "executability": s.get("executability", 1),
                        "total": (
                            s.get("faithfulness", 1)
                            + s.get("completeness", 1)
                            + s.get("executability", 1)
                        ),
                        "reason": s.get("reason", ""),
                    }
                    scored.append(entry)
                else:
                    logger.warning("评分索引超出范围: %d", idx)

        except Exception as exc:
            logger.exception("评分批次 %d 失败", batch_num)
            # 失败的给默认低分，不丢弃
            for s in batch:
                s["_score"] = {
                    "faithfulness": 1,
                    "completeness": 1,
                    "executability": 1,
                    "total": 3,
                    "reason": f"评分失败: {exc}",
                }
                scored.append(s)

    logger.info("评分完成: %d 条样本已评分", len(scored))
    return scored


# ── 去重 ─────────────────────────────────────────────────────

def _jaccard_similarity(text_a: str, text_b: str) -> float:
    """字符级 Jaccard 相似度（基于 2-gram 字符集）。"""
    def char_bigrams(s: str) -> set:
        return {s[i : i + 2] for i in range(len(s) - 1)}

    set_a = char_bigrams(text_a)
    set_b = char_bigrams(text_b)
    if not set_a or not set_b:
        return 0.0
    return len(set_a & set_b) / len(set_a | set_b)


def deduplicate(samples: list[dict], threshold: float = 0.85) -> list[dict]:
    """基于需求文本 Jaccard 相似度去重，保留评分更高的。

    如果两条需求文本的 2-gram Jaccard ≥ threshold，视为近似重复。
    """
    if not samples:
        return []

    # 按评分降序排列，先处理高质量样本
    sorted_samples = sorted(
        samples,
        key=lambda s: s.get("_score", {}).get("total", 0),
        reverse=True,
    )

    kept: list[dict] = []
    removed = 0

    for sample in sorted_samples:
        req_text = sample.get("requirement_doc", "")
        is_dup = False
        for k in kept:
            sim = _jaccard_similarity(req_text, k.get("requirement_doc", ""))
            if sim >= threshold:
                is_dup = True
                break
        if is_dup:
            removed += 1
        else:
            kept.append(sample)

    logger.info("去重完成: %d → %d 条（移除 %d 条重复）", len(samples), len(kept), removed)
    return kept


# ── 评分过滤 ─────────────────────────────────────────────────

def filter_by_score(samples: list[dict], min_total: float = 4.0) -> list[dict]:
    """按三个维度平均分过滤，avg ≥ min_total 保留。

    例如 min_total=4.0 表示 faithfulness+completeness+executability 总分 ≥ 12。
    """
    passed: list[dict] = []
    failed = 0
    for s in samples:
        total = s.get("_score", {}).get("total", 1)
        if total >= min_total * 3:
            passed.append(s)
        else:
            failed += 1
    logger.info("评分过滤: %d 通过 / %d 淘汰 (阈值 avg≥%.1f)", len(passed), failed, min_total)
    return passed


# ── 结构校验 ─────────────────────────────────────────────────

_REQUIRED_FIELDS = {"id", "title", "type", "precondition", "steps", "expected"}

def validate_structure(samples: list[dict]) -> list[dict]:
    """过滤掉缺少必需字段的用例。"""
    valid: list[dict] = []
    invalid_count = 0
    for s in samples:
        cases = s.get("cases", [])
        if not isinstance(cases, list) or len(cases) == 0:
            invalid_count += 1
            continue
        s["cases"] = [
            c for c in cases
            if isinstance(c, dict) and _REQUIRED_FIELDS.issubset(c.keys())
        ]
        if s["cases"]:
            valid.append(s)
        else:
            invalid_count += 1
    logger.info("结构校验: %d 有效 / %d 无效（缺字段或无用例）", len(valid), invalid_count)
    return valid


# ── 完整过滤流程 ─────────────────────────────────────────────

def run_filter_pipeline(
    input_path: str,
    output_dir: str,
    min_total: float = 4.0,
    dedup_threshold: float = 0.85,
) -> tuple[int, int]:
    """执行完整过滤流程：去重 → 评分 → 过滤 → 结构校验。

    Returns:
        (输入样本数, 输出样本数)
    """
    client = get_client()
    samples = load_json(input_path)
    logger.info("过滤流程开始: 输入 %d 条", len(samples))
    input_count = len(samples)

    # 1) 评分（含断点续跑）
    scored_path = os.path.join(output_dir, "scored.json")
    if os.path.exists(scored_path):
        logger.info("使用已有评分结果: %s", scored_path)
        scored = load_json(scored_path)
    else:
        scored = score_quality(client, samples)
        os.makedirs(output_dir, exist_ok=True)
        save_json(scored, scored_path)

    # 2) 去重 + 过滤 + 结构校验
    deduped = deduplicate(scored, threshold=dedup_threshold)
    filtered = filter_by_score(deduped, min_total=min_total)
    valid = validate_structure(filtered)

    # 落盘
    filtered_path = os.path.join(output_dir, "filtered_dataset.json")
    save_json(valid, filtered_path)

    total = sum(item["case_count"] for item in valid)
    logger.info("过滤流程完成: 输入 %d → 输出 %d 条样本 (%d 条用例) → %s",
                input_count, len(valid), total, filtered_path)
    return input_count, len(valid)
