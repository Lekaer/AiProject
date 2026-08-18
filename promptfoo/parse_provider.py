"""promptfoo python provider：parse_requirement 结构评测（M2-5）。

vars.source 为项目根相对路径（或裸需求文本），返回解析是否通过校验 + 结构统计，
供 assertions/parse.js 做"结构合法性 + 关键元素存在性"断言。
注意：parse 输出跨轮不稳定（temperature=0 也会变），元数据只放结构性事实。
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
    from AiLearning.capabilities.requirement_parse import parse_requirement

    source = context.get("vars", {}).get("source") or prompt
    if not os.path.isabs(source):
        candidate = os.path.join(_PROJECT_ROOT, source)
        if os.path.exists(candidate):
            source = candidate

    try:
        model = parse_requirement(source)
    except Exception as e:
        return {"output": "", "metadata": {"valid": False, "error": f"{type(e).__name__}: {e}"}}

    return {
        "output": model.summary,
        "metadata": {
            "valid": True,
            "stats": model.stats(),
            "open_questions": model.open_questions,
            "flow_ids": [f.id for f in model.flows],
            "task_types": [t.type for f in model.flows for t in f.tasks],
        },
    }
