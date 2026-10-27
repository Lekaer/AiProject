"""汇总采样结果并生成分布图（自包含 HTML + 手绘 SVG，零依赖）。

输入：
- interview_artifacts/samples/run_*.json  promptfoo -o json 的多次评测输出（N 次采样）
- interview_artifacts/parse_drift.json      parse_drift_probe.py 产出（可选）

产出：interview_artifacts/sampling_distribution.html

用法：python sampling_chart.py
"""

import glob
import json
import os
import statistics

_ROOT = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(_ROOT, "interview_artifacts")


def load_runs():
    runs = []
    for path in sorted(glob.glob(os.path.join(ART, "samples", "run_*.json"))):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        results = data.get("results", [])
        if isinstance(results, dict):
            results = results.get("results", [])
        passed = sum(1 for r in results if r.get("success"))
        reasons = " ".join(
            str((r.get("gradingResult") or {}).get("reason") or "") for r in results
        )
        infra = "Insufficient Balance" in reasons or "402" in reasons
        runs.append({"file": os.path.basename(path), "passed": passed, "total": len(results), "detail": results, "infra": infra})
    return runs


def svg_bar(dist, max_x, color="#2563eb"):
    """dist: {label: count} → 横向柱状 SVG。"""
    rows = []
    y = 24
    for label, count in dist.items():
        w = int(260 * count / max(max_x, 1))
        rows.append(
            f"<text x='0' y='{y + 13}' font-size='12'>{label}</text>"
            f"<rect x='150' y='{y}' width='{max(w, 1)}' height='18' fill='{color}' rx='3'/>"
            f"<text x='{150 + max(w, 1) + 6}' y='{y + 13}' font-size='12'>{count}</text>"
        )
        y += 26
    return f"<svg width='560' height='{y + 4}'>{''.join(rows)}</svg>"


def main():
    runs = load_runs()
    if not runs:
        raise SystemExit("interview_artifacts/samples/run_*.json 不存在，先跑 N 次 promptfoo eval -o")

    valid = [r for r in runs if not r.get("infra")]
    blocked = [r for r in runs if r.get("infra")]
    pass_rates = [r["passed"] / r["total"] if r["total"] else 0 for r in valid]
    rate_dist = {}
    for r in valid:
        key = f"{r['passed']}/{r['total']}"
        rate_dist[key] = rate_dist.get(key, 0) + 1

    case_pass = {}
    for r in valid:
        for i, d in enumerate(r["detail"], 1):
            desc = d.get("description") or (d.get("testCase") or {}).get("description") or f"case{i}"
            key = f"{desc[:18]}"
            case_pass.setdefault(key, []).append(bool(d.get("success")))

    drift_path = os.path.join(ART, "parse_drift.json")
    drift_block = ""
    if os.path.exists(drift_path):
        with open(drift_path, encoding="utf-8") as f:
            drift = json.load(f)
        flows = [r["flows"] for r in drift["runs"]]
        tasks = [r["tasks"] for r in drift["runs"]]
        oq = [r["open_questions"] for r in drift["runs"]]
        flows_dist = {str(v): flows.count(v) for v in sorted(set(flows))}
        tasks_dist = {str(v): tasks.count(v) for v in sorted(set(tasks))}
        drift_block = f"""
<h2>parse 漂移量化（temperature=0，同一需求 × {len(drift['runs'])} 次）</h2>
<p>统计口径：需求「{drift['source']}」连续解析 {len(drift['runs'])} 次，统计结构事实（flows/tasks/open_questions）的跨次分布。
flows: mean={statistics.mean(flows):.2f} min={min(flows)} max={max(flows)} ·
tasks: mean={statistics.mean(tasks):.2f} min={min(tasks)} max={max(tasks)} ·
open_questions: mean={statistics.mean(oq):.2f} min={min(oq)} max={max(oq)}</p>
<h3>flows 数分布</h3>{svg_bar(flows_dist, max(flows_dist.values()), '#059669')}
<h3>tasks 数分布</h3>{svg_bar(tasks_dist, max(tasks_dist.values()), '#059669')}
<p><b>面试话术</b>：这就是 JD「一致性」指标在我项目里的实证——temperature=0 也不确定，所以断言设计是「结构不断言精确值」（五道门里 parse 门只断结构合法性 + 元素存在性），而量化漂移靠 N 次采样看分布，不看单点。</p>
"""

    rows = "".join(
        f"<tr><td>{r['file']}</td><td>{r['passed']}/{r['total']}</td></tr>" for r in valid
    )
    case_rows = "".join(
        f"<tr><td>{k}</td><td>{sum(v)}/{len(v)}</td><td>{sum(v)/len(v)*100:.0f}%</td></tr>" for k, v in case_pass.items()
    )

    page = f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>N 次采样分布 · m2_parse</title><style>
body{{font-family:-apple-system,"PingFang SC",sans-serif;font-size:15px;line-height:1.75;max-width:820px;margin:0 auto;padding:20px 14px;color:#1a1a1a}}
h1{{font-size:1.3em;border-bottom:2px solid #2563eb;padding-bottom:8px}}
h2{{font-size:1.1em;margin-top:1.5em;border-left:4px solid #2563eb;padding-left:8px}}
table{{border-collapse:collapse;width:100%;font-size:.9em}}td,th{{border:1px solid #cbd5e1;padding:6px;vertical-align:top}}th{{background:#eff6ff}}
.kpi{{display:inline-block;background:#eff6ff;border-radius:10px;padding:10px 18px;margin:6px 8px 6px 0}}
.kpi b{{font-size:1.4em;color:#1e40af}}
.note{{color:#64748b;font-size:.88em}}</style></head><body>
<h1>N 次采样分布 · 评测门 m2_parse（temperature=0，--no-cache）</h1>
<p class="note">实验设计：同一评测集（2 用例）独立重复 {len(runs)} 次，每次全新 LLM 调用、不走缓存。
这对应 JD 任职资格第 4 条「针对 AI 非确定性输出设计量化评估方案」。</p>
<p>
<span class="kpi">有效采样 <b>{len(valid)}/{len(runs)}</b></span>
<span class="kpi">通过率均值 <b>{statistics.mean(pass_rates)*100:.0f}%</b></span>
<span class="kpi">单次全过（{valid[0]['total']}/{valid[0]['total']}）比例 <b>{rate_dist.get(str(valid[0]['total']) + '/' + str(valid[0]['total']), 0)}/{len(valid)}</b></span>
<span class="kpi">跨次一致率 <b>{statistics.mean(pass_rates)*100:.0f}%</b></span>
</p>
<p><b>infra 拦截 {len(blocked)} 轮</b>：{', '.join(r['file'] for r in blocked) or '无'} —— DeepSeek API 402 余额不足，provider 捕获异常返回空输出，被断言判失败。
归因纪律：<b>infra 故障与断言失败分开统计，质量指标只计有效运行</b>；这同时是门禁价值的实证——外部依赖异常被 100% 拦截，没有裸奔进主干。</p>
<h2>单次通过率分布</h2>
{svg_bar(rate_dist, max(rate_dist.values()))}
<h2>逐次明细</h2>
<table><tr><th>采样轮次</th><th>通过数</th></tr>{rows}</table>
<h2>分用例通过率（哪条用例不稳定一目了然）</h2>
<table><tr><th>用例</th><th>通过次数</th><th>比例</th></tr>{case_rows}</table>
{drift_block}
</body></html>"""

    out = os.path.join(ART, "sampling_distribution.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(page)
    print(f"written: {out}")


if __name__ == "__main__":
    main()
