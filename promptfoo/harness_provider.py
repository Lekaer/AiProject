"""promptfoo python provider：把 prompt 接到 capabilities.testcase_design.run()。

promptfoo 约定：实现 call_api(prompt, options, context)，返回
{"output": ..., "metadata": {...}}。metadata 里的 called_tools/steps/stop_reason
供 JS 轨迹断言使用。

provider 由 promptfoo 以独立 python 进程加载，这里显式加载项目根 .env，
保证 DEEPSEEK_API_KEY 一定可用（不依赖调用方的 shell 环境）。
"""

import os
import sys

# 项目根加入 sys.path，保证能 import AiLearning / config
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# 显式加载项目根 .env（config.py 里也有兜底加载，双保险）
try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))
except Exception:
    pass


def call_api(prompt: str, options: dict, context: dict) -> dict:
    from AiLearning.capabilities import testcase_design

    try:
        result = testcase_design.run(prompt)
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
