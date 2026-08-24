# AGENTS.md

本文件为 coding agent 提供本仓库的工作指引。CLAUDE.md 仅作指针，以此文件为准。

## 项目简介

FastAPI 应用（`main.py`），两条平行架构：

1. **新版：通用 agent harness + capabilities**（当前主战场，M1 完成、M2 进行中）
   - `AiLearning/harness/`：与具体能力无关的最小骨架——`loop.py`（agent loop）、`tools.py`（工具注册表 + 通用工具 rag_search/write_output）、`trace.py`（JSONL 轨迹）
   - `AiLearning/capabilities/`：能力层。`testcase_design.py`（用例设计 agent）、`tools.py`（capability 专属工具，如 load_skill）
   - `traces/`：运行轨迹（JSONL）；`outputs/`：生成产物（write_output 沙箱根）
2. **旧版：多阶段 workflow**（保留作 fallback，不再迭代）
   - `AiLearning/agents/`（BaseAgent 三子类：rag/learning/testcase）、`AiLearning/router/`（三级 dispatch：显式 app → 关键词 → LLM 意图识别）、`AiLearning/prompts/`、`AiLearning/rag/`（ChromaDB + BM25 + RRF 混合检索）、`AiLearning/synthesis/`

无数据库；LLM 为 DeepSeek（`config.py` 读 `.env`，key 不入库）。

## 架构纪律（改动必须遵守）

- 四层解耦：harness / 工具 / skill / 评测。**harness 包不得 import capabilities/ 或任何用例生成逻辑**；capability 专属工具注册在 `capabilities/tools.py`，由 capability 组合 `build_generic_registry()` + 专属工具
- 新 capability = 新 skill + 新工具插拔，不起新系统
- 每个 capability 必须同步交付 promptfoo 评测集
- LLM 调用 `temperature=0`（agent 任务要求确定性）

## 常用命令

```bash
# 一律用项目 .venv（python 3.x，依赖已装）
source .venv/bin/activate

# 起服务（热重载）
uvicorn main:app --reload

# 独立脚本（从项目根用 -m）
python -m AiLearning.agents.test

# RAG 单元测试
python -m pytest AiLearning/rag/tests/ -v

# M1 轨迹评测（3 条用例，断言 load_skill 精确集合 + write_output + steps≤10）
promptfoo eval -c promptfoo/m1_trajectory.yaml --no-cache

# M2 评测（parse 结构 + 任务级 skill 纪律）
promptfoo eval -c promptfoo/m2_parse.yaml --no-cache
promptfoo eval -c promptfoo/m2_skill_discipline.yaml --no-cache

# M3 评测（缺陷召回金标准——纯检索零 LLM 成本；对抗审查）
promptfoo eval -c promptfoo/m3_defect_recall.yaml --no-cache
promptfoo eval -c promptfoo/m3_review.yaml --no-cache
```

## 合入质量门（评测即契约）

任何改动 harness / capabilities / skills 的代码或 prompt，合入前必须评测全绿：
`m1_trajectory.yaml`（M1 回归）+ `m2_parse.yaml` + `m2_skill_discipline.yaml` + `m3_defect_recall.yaml`（缺陷库相关改动必跑）+ `m3_review.yaml`（审查/管线改动必跑）。
评测挂了先查根因再改，不允许跳过；先分 error（infra flake）与 failed（断言）再归因。

## 缺陷知识库纪律（M3-1）

- 缺陷记录写在 `data/defects/defects.jsonl`（schema 见 `AiLearning/docs/defect_knowledge_design.md`）：现象先行、根因用枚举、`dimension` 必填
- 改完数据必须重跑灌库：`python -m AiLearning.rag.ingest_defects`（全量重建，只灌 active）
- 模块重构/下线时，把该模块记录批量标 `archived`（不删除）
- 管线在任务级生成前自动检索缺陷库并注入 prompt；`rag_search` 仅为模型临时补查手段



## 环境坑（踩过，别再踩）

- **deepseek-v4-pro 是推理模型**：reasoning tokens 计入 max_tokens，给小了会返回空 content；`max_tokens` 默认 16000 起
- promptfoo 的 python provider 需配 `pythonExecutable` 指向 `.venv/bin/python`
- 旧 API key 曾硬编码在 config.py 并留在 git 历史中——**如需推送远端，先轮换 key**

## 验证习惯

- 改 harness/capabilities 后：先 `python -c "from main import app"` 冒烟，再跑对应 promptfoo 评测
- 评测要 `--no-cache` 复跑确认稳定，不凭单次绿就收尾
