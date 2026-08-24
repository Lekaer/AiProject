"""业务模型持久化存储。

每个 (project_id, kb_name) 对应一个目录，存储 latest.json + 时间戳版本文件。
"""

import hashlib
import json
import os
from datetime import datetime, timezone

from AiLearning.skills.business_model import model_to_dict

# 存储根目录（项目根目录下的 model_store/）
MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "model_store")


def _safe_name(name: str) -> str:
    """将包含特殊字符的名称转为安全的文件系统名称。"""
    # 取 md5 前 10 位 + 保留可读字符
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    h = hashlib.md5(name.encode()).hexdigest()[:8]
    return f"{safe}_{h}"


def _model_dir(pid: str, kb_name: str) -> str:
    return os.path.join(MODEL_DIR, _safe_name(pid), _safe_name(kb_name))


def save_model(pid: str, kb_name: str, model, req_text: str, tech_text: str = "") -> str:
    """保存业务模型到文件系统。

    model 可以是 dataclass (BusinessModel) 或 dict，内部统一转为 dict 序列化。
    req_text / tech_text 为生成该模型时的原始需求和技术文档文本。

    写入 latest.json（覆盖）和时间戳版本文件。
    返回时间戳字符串。
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    data = {
        "model": model if isinstance(model, dict) else model_to_dict(model),
        "requirement": req_text,
        "tech_doc": tech_text,
        "timestamp": ts,
    }

    d = _model_dir(pid, kb_name)
    os.makedirs(d, exist_ok=True)

    # 写入时间戳版本
    version_path = os.path.join(d, f"{ts}.json")
    with open(version_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 写入 latest
    latest_path = os.path.join(d, "latest.json")
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return ts


def load_latest(pid: str, kb_name: str) -> dict | None:
    """加载最新的业务模型，不存在则返回 None。"""
    latest_path = os.path.join(_model_dir(pid, kb_name), "latest.json")
    if not os.path.exists(latest_path):
        return None
    with open(latest_path, encoding="utf-8") as f:
        return json.load(f)


def list_versions(pid: str, kb_name: str) -> list[str]:
    """列出所有版本的时间戳，按时间倒序排列。"""
    d = _model_dir(pid, kb_name)
    if not os.path.isdir(d):
        return []
    versions = []
    for fname in os.listdir(d):
        if fname.endswith(".json") and fname != "latest.json":
            versions.append(fname[:-5])  # 去掉 .json 后缀
    versions.sort(reverse=True)
    return versions


def delete_model(pid: str, kb_name: str):
    """删除指定 KB 的整个模型目录。"""
    import shutil
    d = _model_dir(pid, kb_name)
    if os.path.isdir(d):
        shutil.rmtree(d)
