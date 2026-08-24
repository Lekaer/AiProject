"""promptfoo python provider：任务级生成评测（M2-5）。

vars 直接给 flow/task 的 JSON（绕过 parse，保证评测的输入确定性——
parse 的不稳定性不传导进 skill 纪律评测），跑 task_case_design.run_for_task，
返回 called_tools 供 assertions/skill_discipline.js 判定。
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
    from AiLearning.capabilities import task_case_design
    from AiLearning.capabilities.requirement_model import Flow, Task

    vars_ = context.get("vars", {})
    try:
        flow = Flow.model_validate_json(vars_["flow_json"])
        task = Task.model_validate_json(vars_["task_json"])
        result = task_case_design.run_for_task(flow, task)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

    return {
        "output": result["output"],
        "metadata": {
            "called_tools": result["called_tools"],
            "steps": result["steps"],
            "stop_reason": result["stop_reason"],
            "trace_file": result["trace_file"],
        },
    }
