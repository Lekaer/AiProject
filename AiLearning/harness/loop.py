"""最小 agent loop：perceive → decide → act → observe。

维护一条 messages 会话，每轮调 LLM：
- 模型请求工具（tool_calls）→ 执行工具，把结果作为 observation 追加回会话，继续下一轮；
- 模型直接回复文本 → 视为最终回答，终止；
- 达到 max_steps 仍未终止 → 以 max_steps 原因结束。

工具调用方式决策（2026-08 实测）：DeepSeek 端点（deepseek-v4-pro）原生支持
OpenAI tools 参数（finish_reason=tool_calls、tool_calls 结构完整），
因此使用原生 tool calling，未启用 JSON action 降级协议。若未来端点行为退化，
在本文件加 JSON action 协议分支即可，loop 结构不变。

注意：deepseek-v4-pro 是推理模型，reasoning tokens 计入 max_tokens，
所以 max_tokens 默认值要给足，否则可能出现 content 为空的情况。
"""

import json
import time

from AiLearning.harness.llm import default_model, get_client
from AiLearning.harness.tools import ToolRegistry
from AiLearning.harness.trace import TraceRecorder


def run_loop(
    system_prompt: str,
    task: str,
    tools: ToolRegistry,
    max_steps: int = 10,
    model: str | None = None,
    max_tokens: int = 16000,
    run_id: str | None = None,
) -> dict:
    """跑一个完整的 agent loop。

    Returns:
        {
            "output": 最终回答文本（error 时为错误信息）,
            "steps": 实际执行的 LLM 轮数,
            "stop_reason": "final" | "max_steps" | "error",
            "trace_file": 轨迹文件路径,
        }
    """
    model = model or default_model()
    trace = TraceRecorder(run_id=run_id)
    trace.run_start(task=task, max_steps=max_steps)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]
    client = get_client()

    def finish(output: str, steps: int, stop_reason: str) -> dict:
        trace.run_end(steps=steps, stop_reason=stop_reason)
        return {
            "output": output,
            "steps": steps,
            "stop_reason": stop_reason,
            "trace_file": trace.path,
        }

    for step in range(1, max_steps + 1):
        # ── decide：调 LLM，让它选择直接回答或调用工具 ──
        t0 = time.perf_counter()
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools.schemas(),
                tool_choice="auto",
                temperature=0,  # agent 任务要求确定性，固定为 0
                max_tokens=max_tokens,
            )
        except Exception as e:
            return finish(f"LLM 调用失败：{type(e).__name__}: {e}", step, "error")
        elapsed = time.perf_counter() - t0

        choice = response.choices[0]
        msg = choice.message
        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens or 0,
                "completion_tokens": response.usage.completion_tokens or 0,
                "total_tokens": response.usage.total_tokens or 0,
            }
        trace.llm_call(model=model, n_messages=len(messages), elapsed=elapsed, usage=usage)

        # ── 无工具调用：模型给出最终回答，loop 终止 ──
        if not msg.tool_calls:
            return finish(msg.content or "", step, "final")

        # ── act + observe：执行工具，结果作为 observation 追加回会话 ──
        # 先把 assistant 的工具请求原样入列（只保留必要字段，不回放 reasoning 字段）
        messages.append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ],
        })
        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError as e:
                result = f"错误：工具参数不是合法 JSON（{e}）"
                args = {"_raw": tc.function.arguments}
                trace.tool_call(name=name, args=args, elapsed=0.0, result=result)
            else:
                t1 = time.perf_counter()
                result = tools.execute(name, args)
                trace.tool_call(name=name, args=args, elapsed=time.perf_counter() - t1, result=result)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return finish(messages[-1].get("content") or "", max_steps, "max_steps")
