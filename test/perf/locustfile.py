"""压测最小实践：AiLearning FastAPI 服务（P 族题配套实验）。

目标：走完"基线 → 阶梯加压 → 找拐点 → 对比优化 → 复测"全流程。
用法：
  1. 启动服务：.venv/bin/uvicorn main:app --port 8000 --workers 1
  2. 阶梯加压（每档 60-90s，记录报告）：
     .venv/bin/locust -f test/perf/locustfile.py --headless \
       -u 10 -r 2 -t 90s --host http://127.0.0.1:8000 \
       --csv test/perf/results_u10
  3. 换 -u 25 / 50 / 100 重复；改 --workers 2 复测对比。

场景建模说明（面试要讲）：
- GET /api/kb 权重 3：轻量真实接口（模拟"读多"的列表查询）
- GET /        权重 1：静态页（近似框架开销下限，作对照）
- /api/ask 等 LLM 接口不压：外部依赖贵且慢，压它测的是 DeepSeek 不是我们
"""
from locust import HttpUser, task, between


class ApiUser(HttpUser):
    wait_time = between(0.01, 0.05)  # 思考时间（压服务端极限时调小；模拟真人节奏用 0.1-0.5）

    @task(3)
    def list_kbs(self):
        # 服务要求 X-Project-Id 头（多租户隔离）
        self.client.get("/api/kb", headers={"X-Project-Id": "perf-test"}, name="/api/kb [列表]")

    @task(1)
    def index(self):
        self.client.get("/", name="/ [静态页]")
