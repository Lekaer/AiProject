"""通用 agent harness：与具体 capability 无关的最小骨架。

- loop.py   : agent loop（perceive → decide → act → observe）
- tools.py  : 工具注册表 + harness 通用工具（rag_search、write_output）
- trace.py  : JSONL 轨迹记录

约束：本包不得 import capabilities/ 或任何用例生成逻辑。
capability 专属工具（load_skill 等）见 capabilities/tools.py。
"""

from AiLearning.harness.loop import run_loop
from AiLearning.harness.tools import Tool, ToolRegistry, build_generic_registry
from AiLearning.harness.trace import TraceRecorder, read_trace

__all__ = [
    "run_loop",
    "Tool",
    "ToolRegistry",
    "build_generic_registry",
    "TraceRecorder",
    "read_trace",
]
