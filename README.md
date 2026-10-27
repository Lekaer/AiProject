# AI 驱动的测试用例生成 Agent（AiLearning）

从需求文档到测试用例的端到端 Agent 系统：需求结构化 → 按测试维度生成用例 → 缺陷知识库注入 → 对抗审查找覆盖缺口 → 评测质量门兜底。配套完整的 promptfoo 评测体系，"评测全绿才合入"。

## 核心设计

- **自研最小 agent harness**：loop（工具调用驱动的控制循环）+ tools（注册/分发/异常转 observation）+ trace（JSONL 轨迹，字段对齐 OpenTelemetry `gen_ai.*`）+ capability（薄业务层，只做 prompt 组装）
- **需求结构化模型**：PRD → Flow/Task/Rule 三级模型（Rule = condition + expected），全链路 ID 可追溯，缺失信息三段式处理（可推断标 assumed / 不可推断进 open_questions / 生成照常）
- **双层用例生成**：任务级点用例（节点级维度选择 + 缺陷库注入）+ 流程级场景用例（主干 + 单点变异）
- **混合检索缺陷知识库**：ChromaDB 向量 + BM25 + RRF 融合，按任务结构化字段程序构造查询，金标准 hit rate 7/7
- **对抗审查**：red-team pass 审查生成结果的覆盖缺口，缺口定位到具体 rule_id，支持缺口 → 再生成闭环（evaluator-optimizer）
- **评测质量门**：5 道 promptfoo 评测门（轨迹回归 / parse 结构 / skill 纪律 / 缺陷召回 / 对抗审查），断言失败退出码非零可直接作 CI 门禁。最近全绿：2026-10-26（LLM 相关门）；缺陷召回为纯检索门零 LLM 成本，本地可随时回归

## 评测工具与演示产物

- `trace_replay_html.py`：traces/*.jsonl → 独立 HTML 回放页（逐步展示 agent 的工具调用与决策）
- `parse_drift_probe.py`：同输入 N 次生成，量化输出漂移（temp=0 下仍有 tasks 数 2~4 的漂移，实证"确定性采样≠确定性输出"）
- `sampling_chart.py`：promptfoo 多次采样结果 → SVG 分布图（有效运行与 infra 拦截分开归因）
- `interview_artifacts/`：演示产物合集——五道评测门 HTML 报告、trace 回放页、N=10 采样分布、漂移探针结果

## 下一步路线（2026-10-27 定）

用例可执行化：NL 用例 → 用例 DSL（白名单约束翻译层）→ 自动执行 → 变异断言评测。设计文档见 ai-exec/PLAN.md（另库）。

## 技术栈

Python / FastAPI / DeepSeek（tool calling）/ ChromaDB + BM25 / pydantic / promptfoo

## 快速开始

```bash
# 环境准备
pip install -r requirements.txt
cp .env.example .env   # 填入 DEEPSEEK_API_KEY

# 端到端跑一篇需求文档
python main.py         # FastAPI 服务（含用例生成页面）

# 跑评测质量门（合入前必过）
promptfoo eval -c promptfoo/m1_trajectory.yaml --no-cache
promptfoo eval -c promptfoo/m2_parse.yaml --no-cache
promptfoo eval -c promptfoo/m2_skill_discipline.yaml --no-cache
promptfoo eval -c promptfoo/m3_defect_recall.yaml --no-cache
promptfoo eval -c promptfoo/m3_review.yaml --no-cache
```

## 目录结构

```
AiLearning/
  harness/       # agent 运行时：loop / tools / trace / llm
  capabilities/  # 业务层：需求解析、用例生成、对抗审查、管线
  skills/        # 测试维度 skill 定义（description 即触发器）
  rag/           # 检索：向量库 / BM25 / RRF 融合 / 缺陷库
  docs/          # 设计文档
promptfoo/       # 评测配置与 provider / JS 断言
main.py          # FastAPI 入口
```

## 设计决策摘录

- **workflow 主干 + agent 决策点**：管线主干用代码编排（吞吐工程交给模型只会更慢更贵），维度选择等模糊决策点才交给 agent loop
- **规则能做的不用模型**：检索查询由程序按任务字段构造，不靠模型选词；模型只做语义判断
- **评测即契约**：任何 harness/capability/prompt 改动，五道评测门全绿才允许合入
- **异常即 observation**：工具异常转成字符串喂回模型自纠错，而不是炸掉整个 loop

> 个人学习项目，用于探索 AI 原生测试工作流与 LLM 应用质量保障。
