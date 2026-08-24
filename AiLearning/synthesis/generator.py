"""数据合成生成器：Self-Instruct 需求变体 + 调用 Agent 生成用例。

用法：
    python -m AiLearning.synthesis.generator --output data/synthesis/2026-07-13

流程：
    1. 加载种子需求
    2. 用 DeepSeek 将种子扩展为 N 条变体需求
    3. 每条变体调用 TestCaseDesignAgent 生成用例（跳过 Phase 0）
    4. 每阶段落盘中间文件，支持断点续跑
"""

import json
import logging
import os
import sys
import time as time_module
from dataclasses import asdict
from pathlib import Path
from typing import Generator

from AiLearning.agents.testcase_design_agent import TestCaseDesignAgent
from AiLearning.prompts.synthesis import DEFAULT_VARIATION_PROMPT
from AiLearning.service import get_client

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_TARGET_COUNT = 20
DEFAULT_MAX_WORKERS = 2
DEFAULT_KB_NAME = "eval_kb"

# 中间文件名
FILE_VARIANTS = "variants.json"
FILE_CASES = "cases.json"


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _parse_json_list(raw: str) -> list:
    """从 LLM 响应中提取 JSON 数组，3 级 fallback。"""
    import re

    text = raw.strip()
    # 1) 直接解析
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    # 2) markdown code fence
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    # 3) 查找第一个 JSON 数组
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    logger.warning("无法解析 LLM 响应中的 JSON 数组: %s", text[:300])
    return []


class SynthesisGenerator:
    """数据合成编排器。"""

    def __init__(self, output_dir: str):
        self.client = get_client()
        self.agent = TestCaseDesignAgent()
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ── 需求变体扩展 ─────────────────────────────────────────

    def expand_requirements(
        self,
        seed_requirements: list[dict],
        target_count: int = DEFAULT_TARGET_COUNT,
    ) -> list[dict]:
        """用 Self-Instruct 将种子需求扩展为变体需求。

        3 条种子分 2 批调用：每批取 1-2 条种子作为上下文，
        让 LLM 在不同批次聚焦不同业务模式，避免变体同质化。
        """
        all_variants: list[dict] = []

        per_batch = max(1, target_count // 2)

        for batch_idx in range(0, len(seed_requirements), 2):
            batch_seeds = seed_requirements[batch_idx : batch_idx + 2]
            batch_target = per_batch if batch_idx + 2 < len(seed_requirements) else target_count - len(all_variants)
            if batch_target <= 0:
                break

            # 组装种子文本
            seed_parts = []
            for i, seed in enumerate(batch_seeds):
                skill = seed.get("skill", "")
                seed_parts.append(f"种子{i + 1} [skill={skill}]:\n{seed['requirement_doc']}")
            seed_text = "\n\n---\n\n".join(seed_parts)

            logger.info("扩展需求批次 %d: %d 条种子 → %d 条目标", batch_idx // 2 + 1, len(batch_seeds), batch_target)

            prompt = DEFAULT_VARIATION_PROMPT.format(seed_text=seed_text, target_count=batch_target)
            try:
                response = self.client.chat(
                    messages=[
                        {"role": "system", "content": DEFAULT_VARIATION_PROMPT.system},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=65536,
                )
                variants = _parse_json_list(response)
                for v in variants:
                    if (
                        isinstance(v, dict)
                        and v.get("requirement_doc")
                        and v.get("skill")
                    ):
                        all_variants.append(v)
                logger.info("批次 %d 生成 %d 条变体（有效 %d 条）", batch_idx // 2 + 1, len(variants), len(all_variants))
            except Exception:
                logger.exception("批次 %d 生成变体失败", batch_idx // 2 + 1)

        # 落盘
        save_json(all_variants, os.path.join(self.output_dir, FILE_VARIANTS))
        logger.info("需求变体扩展完成，共 %d 条 → %s", len(all_variants), FILE_VARIANTS)
        return all_variants

    # ── 用例生成 ──────────────────────────────────────────────

    def generate_cases(
        self,
        requirements: list[dict],
        kb_name: str = DEFAULT_KB_NAME,
    ) -> list[dict]:
        """逐条需求调用 Agent（跳过 Phase 0），生成用例并收集。"""
        cases_path = os.path.join(self.output_dir, FILE_CASES)

        # 断点续跑：已完成的跳过
        done_hashes = set()
        if os.path.exists(cases_path):
            existing = load_json(cases_path)
            for item in existing:
                done_hashes.add(item.get("_seed_hash", ""))
            logger.info("断点续跑：已有 %d 条用例，跳过重复", len(done_hashes))

        all_cases: list[dict] = list(
            load_json(cases_path) if os.path.exists(cases_path) else []
        )

        for i, req in enumerate(requirements):
            import hashlib

            seed_hash = hashlib.md5(req["requirement_doc"].encode()).hexdigest()
            if seed_hash in done_hashes:
                continue
            skill = req.get("skill", "state_machine")
            logger.info("[%d/%d] 生成用例 skill=%s hash=%s", i + 1, len(requirements), skill, seed_hash[:6])

            try:
                result = self.agent.execute(
                    req["requirement_doc"][:800],
                    requirement_doc=req["requirement_doc"],
                    collection_names=[kb_name] if kb_name else None,
                    skill_pre_selected=skill,
                )

                cases = []
                answer = result.answer
                try:
                    cases = json.loads(answer)
                    if isinstance(cases, str):
                        cases = json.loads(cases)
                except (json.JSONDecodeError, TypeError):
                    pass

                record = {
                    "_seed_hash": seed_hash,
                    "requirement_doc": req["requirement_doc"],
                    "skill": skill,
                    "difficulty": req.get("difficulty", "medium"),
                    "cases": cases if isinstance(cases, list) else [],
                    "case_count": len(cases) if isinstance(cases, list) else 0,
                }
                all_cases.append(record)

                # 每 5 条存一次盘
                if (i + 1) % 5 == 0:
                    save_json(all_cases, cases_path)

            except Exception:
                logger.exception("[%d/%d] 生成用例失败", i + 1, len(requirements))

        save_json(all_cases, cases_path)
        total_cases = sum(item["case_count"] for item in all_cases)
        logger.info("用例生成完成：%d 条需求 → %d 条用例 → %s", len(all_cases), total_cases, FILE_CASES)
        return all_cases

    # ── 主流程 ────────────────────────────────────────────────

    def run_full_pipeline(
        self,
        seed_path: str,
        target_count: int = DEFAULT_TARGET_COUNT,
        kb_name: str = DEFAULT_KB_NAME,
    ) -> str:
        """完整合成流程：加载种子 → 扩展变体 → 生成用例 → 返回产物目录。"""
        t0 = time_module.perf_counter()

        logger.info("=" * 60)
        logger.info("数据合成开始 target=%d output=%s", target_count, self.output_dir)
        logger.info("=" * 60)

        seeds = load_json(seed_path)
        logger.info("加载种子需求 %d 条", len(seeds))

        # Step 1: 扩展变体
        variants = self.expand_requirements(seeds, target_count)

        # Step 2: 生成用例
        cases = self.generate_cases(variants, kb_name)

        elapsed = round(time_module.perf_counter() - t0, 1)
        total_cases = sum(item["case_count"] for item in cases)
        logger.info(
            "=" * 60 + "\n数据合成完成: %d 条需求 → %d 条用例, 耗时 %.1fs\n输出目录: %s",
            len(cases), total_cases, elapsed, self.output_dir,
        )
        return self.output_dir


# ── CLI 入口 ──────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="数据合成生成器")
    parser.add_argument("--output", default=None, help="输出目录")
    parser.add_argument("--seed", default=None, help="种子需求文件路径")
    parser.add_argument("--target", type=int, default=DEFAULT_TARGET_COUNT, help="目标变体数量")
    parser.add_argument("--kb", default=DEFAULT_KB_NAME, help="知识库名称")
    args = parser.parse_args()

    if args.seed:
        seed_path = args.seed
    else:
        root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        seed_path = os.path.join(root, "data", "synthesis", "seed_requirements.json")

    if args.output:
        output_dir = args.output
    else:
        root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        output_dir = os.path.join(root, "data", "synthesis", time_module.strftime("%Y-%m-%d"))

    gen = SynthesisGenerator(output_dir)
    gen.run_full_pipeline(seed_path=seed_path, target_count=args.target, kb_name=args.kb)


if __name__ == "__main__":
    main()
