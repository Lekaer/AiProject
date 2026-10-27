"""把 traces/ 下的 JSONL 轨迹渲染成自包含 HTML 回放页（面试演示产物）。

用法：
    python trace_replay_html.py [traces/xxx.jsonl] [-o 输出.html]

不带参数时取 traces/ 下最新文件。渲染只依赖标准库。
"""

import argparse
import glob
import html
import json
import os

CSS = """
body{font-family:-apple-system,"PingFang SC",sans-serif;font-size:15px;line-height:1.7;max-width:820px;margin:0 auto;padding:20px 14px;color:#1a1a1a}
h1{font-size:1.3em;border-bottom:2px solid #2563eb;padding-bottom:8px}
h2{font-size:1.1em;margin-top:1.5em;border-left:4px solid #2563eb;padding-left:8px}
.meta{background:#f8fafc;border:1px solid #cbd5e1;border-radius:10px;padding:12px 16px;font-size:.92em}
.meta b{color:#b91c1c}
.kpis{display:flex;flex-wrap:wrap;gap:10px;margin:14px 0}
.kpi{flex:1;min-width:110px;background:#eff6ff;border-radius:10px;padding:10px;text-align:center}
.kpi .n{font-size:1.5em;font-weight:bold;color:#1e40af}.kpi .l{font-size:.8em;color:#64748b}
.ev{border-radius:10px;padding:10px 14px;margin:10px 0;border:1px solid #e2e8f0}
.ev .head{font-weight:bold;margin-bottom:4px}
.t0{color:#64748b;font-size:.8em}
.llm{background:#eff6ff;border-left:4px solid #2563eb}
.tool{background:#ecfdf5;border-left:4px solid #059669}
.start{background:#fffbeb;border-left:4px solid #d97706}
.end{background:#fdf2f8;border-left:4px solid #db2777}
pre{background:#f1f5f9;border-radius:8px;padding:8px 10px;overflow-x:auto;font-size:.82em;white-space:pre-wrap;word-break:break-all;margin:6px 0}
.tag{display:inline-block;background:#2563eb;color:#fff;border-radius:6px;padding:1px 8px;font-size:.78em;margin-right:6px}
.note{color:#64748b;font-size:.85em}
table{border-collapse:collapse;width:100%;font-size:.88em}td,th{border:1px solid #cbd5e1;padding:6px;vertical-align:top}th{background:#eff6ff}
"""


def esc(s):
    return html.escape(str(s))


def fmt_args(args):
    try:
        return json.dumps(args, ensure_ascii=False, indent=1)
    except TypeError:
        return str(args)


def render(trace_path):
    events = []
    with open(trace_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))

    start = next((e for e in events if e["event"] == "run_start"), None)
    end = next((e for e in events if e["event"] == "run_end"), None)
    llms = [e for e in events if e["event"] == "llm_call"]
    tools = [e for e in events if e["event"] == "tool_call"]
    t0 = events[0]["ts"] if events else 0

    pt = sum(e.get("gen_ai.usage.prompt_tokens", 0) for e in llms)
    ct = sum(e.get("gen_ai.usage.completion_tokens", 0) for e in llms)

    parts = [
        "<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0'>"
        f"<title>Trace 回放 {esc(start['run_id']) if start else ''}</title><style>{CSS}</style></head><body>",
        f"<h1>Agent Trace 回放 <span class='note'>run_id={esc(start['run_id']) if start else '?'}</span></h1>",
        "<div class='meta'><b>Task：</b>" + esc(start["task"]) + "</div>" if start else "",
        "<div class='kpis'>",
        f"<div class='kpi'><div class='n'>{end['steps'] if end else '-'}</div><div class='l'>steps</div></div>" if end else "",
        f"<div class='kpi'><div class='n'>{(end['total_elapsed_ms']/1000):.1f}s</div><div class='l'>总耗时</div></div>" if end else "",
        f"<div class='kpi'><div class='n'>{pt}</div><div class='l'>prompt tokens</div></div>",
        f"<div class='kpi'><div class='n'>{ct}</div><div class='l'>completion tokens</div></div>",
        f"<div class='kpi'><div class='n'>{len(llms)}</div><div class='l'>LLM 调用</div></div>",
        f"<div class='kpi'><div class='n'>{len(tools)}</div><div class='l'>工具调用</div></div>",
        f"<div class='kpi'><div class='n'>{esc(end['stop_reason']) if end else '-'}</div><div class='l'>stop_reason</div></div>",
        "</div>",
        "<p class='note'>字段遵循 OTel GenAI 语义约定（gen_ai.system / gen_ai.usage.* / gen_ai.tool.*）——面试话术：这就是 JD 里「基于 OTel 等可观测探针采集模型调用、Token、工具链路日志」的最小落地形态。</p>",
        "<h2>事件时间线</h2>",
    ]

    for e in events:
        rel = e["ts"] - t0
        stamp = f"<span class='t0'>+{rel:.1f}s</span>"
        if e["event"] == "run_start":
            parts.append(f"<div class='ev start'><div class='head'>▶ run_start {stamp}</div>max_steps={e.get('max_steps')}</div>")
        elif e["event"] == "llm_call":
            parts.append(
                f"<div class='ev llm'><div class='head'>🧠 llm_call {stamp}</div>"
                f"<span class='tag'>{esc(e.get('gen_ai.request.model'))}</span>"
                f"messages={e.get('gen_ai.request.message_count')} · "
                f"prompt_tokens={e.get('gen_ai.usage.prompt_tokens')} · "
                f"completion_tokens={e.get('gen_ai.usage.completion_tokens')} · "
                f"elapsed={e.get('elapsed_ms')}ms</div>"
            )
        elif e["event"] == "tool_call":
            summary = e.get("result_summary") or ""
            if len(summary) > 600:
                summary = summary[:600] + " …（截断）"
            parts.append(
                f"<div class='ev tool'><div class='head'>🔧 tool_call {stamp} · {esc(e.get('gen_ai.tool.name'))} · {e.get('elapsed_ms')}ms</div>"
                f"<pre>{esc(fmt_args(e.get('gen_ai.tool.args')))}</pre>"
                f"<pre>{esc(summary)}</pre></div>"
            )
        elif e["event"] == "run_end":
            parts.append(
                f"<div class='ev end'><div class='head'>■ run_end {stamp}</div>"
                f"steps={e.get('steps')} · stop_reason={esc(e.get('stop_reason'))} · total={e.get('total_elapsed_ms')}ms</div>"
            )

    parts.append("<h2>Token 明细</h2><table><tr><th>#</th><th>model</th><th>prompt</th><th>completion</th><th>elapsed</th></tr>")
    for i, e in enumerate(llms, 1):
        parts.append(
            f"<tr><td>{i}</td><td>{esc(e.get('gen_ai.request.model'))}</td>"
            f"<td>{e.get('gen_ai.usage.prompt_tokens')}</td><td>{e.get('gen_ai.usage.completion_tokens')}</td>"
            f"<td>{e.get('elapsed_ms')}ms</td></tr>"
        )
    parts.append("</table></body></html>")
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace", nargs="?", help="JSONL 轨迹路径，默认取 traces/ 最新")
    ap.add_argument("-o", "--output", help="输出 HTML 路径，默认打印到 stdout")
    args = ap.parse_args()

    trace = args.trace
    if not trace:
        candidates = glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), "traces", "*.jsonl"))
        if not candidates:
            raise SystemExit("traces/ 下没有 JSONL 文件")
        trace = max(candidates, key=os.path.getmtime)

    page = render(trace)
    out = args.output
    if not out:
        rid = os.path.basename(trace).replace(".jsonl", "")
        out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "interview_artifacts", f"trace_replay_{rid}.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"written: {out}")


if __name__ == "__main__":
    main()
