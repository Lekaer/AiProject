"""parse 漂移量化探针：同一需求 temperature=0 连续解析 N 次，记录结构统计分布。

产出 interview_artifacts/parse_drift.json，供 sampling_chart.py 绘图。
这就是「temperature=0 同一输入三次三个结果」的量化证据（JD 一致性指标）。

用法：python parse_drift_probe.py [--n 10]
"""

import argparse
import json
import os

from dotenv import load_dotenv

_ROOT = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_ROOT, ".env"))

SOURCE = "商户可修改门店营业时间，每天一个时间段，开始时间必须早于结束时间，修改后次日生效。"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    args = ap.parse_args()

    from AiLearning.capabilities.requirement_parse import parse_requirement

    runs = []
    for i in range(args.n):
        model = parse_requirement(SOURCE)
        stats = model.stats()
        runs.append(
            {
                "run": i + 1,
                "flows": len(model.flows),
                "tasks": sum(len(f.tasks) for f in model.flows),
                "open_questions": len(model.open_questions),
                "stats": stats,
            }
        )
        print(f"run {i + 1}: flows={runs[-1]['flows']} tasks={runs[-1]['tasks']} open_questions={runs[-1]['open_questions']}")

    out = os.path.join(_ROOT, "interview_artifacts", "parse_drift.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"source": SOURCE, "temperature": 0, "runs": runs}, f, ensure_ascii=False, indent=1)
    print(f"written: {out}")


if __name__ == "__main__":
    main()
