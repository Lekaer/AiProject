"""promptfoo python provider：对抗审查评测（M3 债 1）。

输入用固定 flow + 固定用例集（cases 直传，不走文件约定），
跑 adversarial_review.run_review，返回缺口数与轨迹供断言。
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
    import json

    from AiLearning.capabilities import adversarial_review
    from AiLearning.capabilities.requirement_model import Flow

    vars_ = context.get("vars", {})
    try:
        flow = Flow.model_validate_json(vars_["flow_json"])
        cases = json.loads(vars_["cases_json"])
        result = adversarial_review.run_review(flow, cases=cases)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

    gap_count = 0
    for call in result["called_tools"]:
        if call["name"] == "write_output":
            try:
                gaps = json.loads(call["args"].get("content", "[]"))
                gap_count = len(gaps) if isinstance(gaps, list) else 0
            except (json.JSONDecodeError, TypeError):
                pass

    return {
        "output": result["output"],
        "metadata": {
            "called_tools": result["called_tools"],
            "stop_reason": result["stop_reason"],
            "gap_count": gap_count,
        },
    }
