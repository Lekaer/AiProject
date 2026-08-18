"""JSONL 轨迹记录。

每次 agent 运行生成一个 traces/<run_id>.jsonl 文件，每行一个事件。
字段命名向 OTel GenAI 语义约定靠拢（gen_ai.*），够用即可，不做完整的 span 模型。

事件类型：
- run_start  : 任务开始（task、max_steps）
- llm_call   : 一次 LLM 调用（model、消息数、耗时、token usage）
- tool_call  : 一次工具执行（name、args、耗时、结果摘要，截断 500 字符）
- run_end    : 运行结束（总步数、终止原因、总耗时）
"""

import json
import os
import time
import uuid

# 工具结果写进轨迹时的最大长度，避免大段检索结果撑爆轨迹文件
RESULT_SUMMARY_MAX_CHARS = 500

# 轨迹目录（仓库根 traces/，已加入 .gitignore）
TRACES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "traces",
)


class TraceRecorder:
    """把一次 agent 运行的关键事件追加写入 JSONL 文件。"""

    def __init__(self, run_id: str | None = None, traces_dir: str | None = None):
        self.run_id = run_id or uuid.uuid4().hex[:12]
        self._t0 = time.perf_counter()
        os.makedirs(traces_dir or TRACES_DIR, exist_ok=True)
        self.path = os.path.join(traces_dir or TRACES_DIR, f"{self.run_id}.jsonl")

    def _write(self, event: str, **fields) -> None:
        record = {
            "event": event,
            "run_id": self.run_id,
            "ts": round(time.time(), 3),
            **fields,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def run_start(self, task: str, max_steps: int) -> None:
        self._write("run_start", task=task, max_steps=max_steps)

    def llm_call(
        self,
        model: str,
        n_messages: int,
        elapsed: float,
        usage: dict | None = None,
    ) -> None:
        usage = usage or {}
        self._write(
            "llm_call",
            **{
                "gen_ai.system": "deepseek",
                "gen_ai.request.model": model,
                "gen_ai.request.message_count": n_messages,
                "gen_ai.usage.prompt_tokens": usage.get("prompt_tokens", 0),
                "gen_ai.usage.completion_tokens": usage.get("completion_tokens", 0),
                "elapsed_ms": round(elapsed * 1000),
            },
        )

    def tool_call(self, name: str, args: dict, elapsed: float, result: str) -> None:
        summary = result
        if len(summary) > RESULT_SUMMARY_MAX_CHARS:
            summary = summary[:RESULT_SUMMARY_MAX_CHARS] + "...[截断]"
        self._write(
            "tool_call",
            **{
                "gen_ai.tool.name": name,
                "gen_ai.tool.args": args,
                "result_summary": summary,
                "elapsed_ms": round(elapsed * 1000),
            },
        )

    def run_end(self, steps: int, stop_reason: str) -> None:
        self._write(
            "run_end",
            steps=steps,
            stop_reason=stop_reason,
            total_elapsed_ms=round((time.perf_counter() - self._t0) * 1000),
        )


def read_trace(path: str) -> list[dict]:
    """读取一个轨迹文件，返回事件列表（按写入顺序）。"""
    events = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events
