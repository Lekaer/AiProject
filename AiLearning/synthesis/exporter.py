"""数据合成导出器：Alpaca 格式导出 + train/val 拆分。"""

import json
import logging
import os
import random

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


def load_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(data, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def export_alpaca(samples: list[dict], output_path: str) -> None:
    """导出为 Alpaca 格式训练数据。

    每条样本格式：
      {
        "instruction": "完整需求描述",
        "input": "",
        "output": "<用例 JSON 字符串>"
      }

    Alpaca 格式兼容 LLaMA-Factory、Firefly、FastChat 等主流微调框架。
    """
    alpaca_data: list[dict] = []
    for s in samples:
        requirement = s.get("requirement_doc", "")
        cases = s.get("cases", [])

        # output 是用例的 JSON 字符串
        output_str = json.dumps(cases, ensure_ascii=False)

        alpaca_data.append({
            "instruction": requirement,
            "input": "",
            "output": output_str,
        })

    save_json(alpaca_data, output_path)
    logger.info("Alpaca 导出: %d 条 → %s", len(alpaca_data), output_path)


def train_val_split(
    data: list[dict],
    val_ratio: float = 0.1,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """随机打乱后拆分为训练集和验证集。"""
    rng = random.Random(seed)
    shuffled = list(data)
    rng.shuffle(shuffled)

    val_size = max(1, int(len(shuffled) * val_ratio))
    train = shuffled[val_size:]
    val = shuffled[:val_size]

    logger.info("数据集拆分: train=%d val=%d (ratio=%.2f)", len(train), len(val), val_ratio)
    return train, val
