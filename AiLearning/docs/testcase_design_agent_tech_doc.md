# TestCaseDesignAgent 技术实现方案

## 1. 概述

在现有 RAG 系统（FastAPI + ChromaDB + 混合检索 + DeepSeek LLM）基础上，新增技能驱动的测试用例设计 Agent。核心思路：**模拟人类测试人员的工作流程**——先掌握业务领域知识，再按测试维度系统化设计用例，先生成测试点再展开为完整用例。

与旧 `TestCaseAgent`（单次 Prompt，单一 KB 检索）共存，通过关键词路由区分。

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           API 层 (main.py)                          │
│  POST /api/kb/{kb_name}/ask                                         │
│  Body: { question, app, requirement_doc?, reference_case_filenames? }│
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        路由层 (agent_router.py)                      │
│  三级调度: 显式app → 关键词匹配 → LLM意图识别                        │
│  关键词: "用例" "测试" "设计用例" → testcase_design                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     TestCaseDesignAgent                             │
│                                                                     │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐            │
│  │  需求文档     │   │  业务文档     │   │  参考用例     │           │
│  │  实时传入     │   │  KB检索       │   │  按名获取     │           │
│  │  split后全用  │   │  混合检索     │   │  get_by_filename│         │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘            │
│         │                  │                   │                    │
│         └──────────┬───────┘                   │                    │
│                    │                           │                    │
│                    ▼                           │                    │
│         ┌──────────────────┐                   │                    │
│         │  main_context    │                   │                    │
│         │  业务知识(地基)   │                   │                    │
│         │  + 新需求(靶心)   │                   │                    │
│         └────────┬─────────┘                   │                    │
│                  │                             │                    │
│     ┌────────────┼────────────┐                │                    │
│     ▼            ▼            ▼                │                    │
│  Phase 0      Phase 1      Phase 2 ◄───────────┘                    │
│  Skill选择    测试点生成    用例展开                                  │
│  1次LLM       ≤3次LLM      每15点1次LLM                              │
│                                                                     │
│     └────────────┼────────────┘                                     │
│                  ▼                                                  │
│         AgentResponse(answer=JSON数组, metadata={...})              │
└─────────────────────────────────────────────────────────────────────┘
```

## 3. 三类文档的使用路径

这是方案的核心设计——三种文档来源不同、角色不同、使用阶段不同：

```
需求文档(实时上传)              业务文档(KB自动检索)           参考用例(用户指定文件名)
      │                                │                              │
      ▼                                ▼                              │
 split_documents()            retrieve(question +                     │
 chunk_size=800               需求前500字, top_k=10)                   │
 全部chunk拼接                        │                              │
      │                                │                              │
      │                        混合检索拉取:                           │
      │                        业务规则/风险/历史缺陷                   │
      │                                │                              │
      ├──────────┬──────────┐         ├──────────┬──────────┐         │
      ▼          ▼          ▼         ▼          ▼          ▼         │
   Phase 0    Phase 1    Phase 2    Phase 0    Phase 1    Phase 2     │
   Skill选择  测试点生成  用例展开   Skill选择   测试点生成  (不使用)   │
                                      │                               │
                                      │                 Phase 2 ONLY  │
                                      │                 用例展开中学习: │
                                      └─────────────────·标题命名习惯  │
                                                         ·步骤细化粒度 │
                                                         ·预期结果句式 │
```

- **需求文档**：决定"测什么"，split 后全部保留，不经检索
- **业务文档**：决定"怎么测"，经混合检索获取，作为 LLM 的领域知识基础
- **参考用例**：决定"写成什么样"，按文件名精确获取，仅 Phase 2 作为风格参考

## 4. Skill 体系

### 数据结构

```python
@dataclass(frozen=True)
class Skill:
    name: str              # "boundary_value"
    display_name: str      # "边界值分析"
    description: str       # 一句话说明
    test_point_rules: str  # Phase 1 生成测试点的规则（自然语言指令）
    test_case_rules: str   # Phase 2 展开用例的规则（自然语言指令）
```

### 6 个 Skill 及批次分组

为减少 LLM 调用次数，按语义相近原则分为 3 组，每组一次调用：

| 批次 | Skill | 关注点 |
|------|-------|--------|
| 边界与异常 | `boundary_value` + `exception_path` | 输入边界、非法值、网络故障、并发冲突 |
| 权限与状态 | `permission_security` + `state_machine` | 认证授权、角色校验、状态转换、幂等 |
| 数据与组合 | `data_consistency` + `combinatorial` | 事务完整性、缓存一致性、跨模块交互 |

### Skill 示例（边界值分析）

```
test_point_rules:
  识别需求文档和业务规则中所有涉及数值、日期、字符串、集合的输入和参数。
  对每个参数生成测试点：
  - 最小边界值 / 最大边界值
  - 边界+1（超出上限）和边界-1（低于下限）
  - 零值、负值（如适用）
  结合业务知识：业务规则中提到的限额、阈值、周期应作为边界值测试的重点。

test_case_rules:
  对每个边界测试点，展开为完整用例：
  - 前置条件必须明确设定边界场景（如当前值为阈值-1）
  - 测试步骤中写明具体输入值和验证方式
  - 预期结果明确：接受并正确处理 / 拒绝并给出错误码 / 系统稳定不崩溃
```

## 5. 三阶段执行流程

```
execute(question, collection_name, requirement_doc?, reference_case_filenames?)
│
├─ Step 1: 需求文档 split(chunk_size=800) → 全部拼接 → requirement_context
├─ Step 2: retrieve(question + 需求前500字, KB, top_k=10) → business_context
├─ Step 3: get_by_filename(filenames) → reference_cases
│
├─ main_context = "## 业务领域知识\n{business_context}\n\n## 新需求文档\n{requirement_context}"
│
├─ ═══════════ Phase 0: Skill选择 (1次 LLM) ═══════════
│   │
│   │ System: "你是一个测试架构师，深入掌握该业务领域"
│   │ Prompt: main_context + skills_catalog
│   │ Output: ["boundary_value", "exception_path", "permission_security", ...]
│   │ Fallback: 全部6个Skill
│   │
│   ▼
├─ ═══════════ Phase 1: 测试点生成 (≤3次 LLM，按批次) ═══════════
│   │
│   │ For each batch in SKILL_BATCHES:
│   │   if batch中有Skill被选中:
│   │     System: "你是一个资深测试工程师，深入掌握该业务领域的知识和规则"
│   │     Prompt: main_context + batch各Skill的test_point_rules
│   │     Output: [{id:"TP-001", skill, title, description, related_context}, ...]
│   │     try/except: 单批次失败不影响其他
│   │
│   ├─ Batch "边界与异常" → [TP-001 ... TP-020]
│   ├─ Batch "权限与状态" → [TP-021 ... TP-035]
│   └─ Batch "数据与组合" → [TP-036 ... TP-049]
│   │
│   ▼
├─ ═══════════ Phase 2: 用例展开 (每15个测试点1次 LLM) ═══════════
│   │
│   │ For chunk in (test_points, batch_size=15):
│   │   System: "你是一个资深测试工程师，擅长将测试点展开为完整用例"
│   │   Prompt: main_context + chunk测试点 + case_rules + reference_cases
│   │   Output: [{id:"TC-001", title, type, precondition, steps, expected}, ...]
│   │   try/except: 单批失败不影响
│   │
│   └─ 合并所有分片 → JSON序列化
│
└─ AgentResponse(answer=<JSON>, metadata={retrieved_docs, selected_skills, ...})
```

**LLM 调用次数分析**：

| 场景 | Phase 0 | Phase 1 | Phase 2(61测试点) | 总计 |
|------|---------|---------|-------------------|------|
| 全 Skill 选中 | 1 | 3 | 5 (61/15) | 9 |
| 部分 Skill 选中 | 1 | 1~2 | 3~4 | 5~7 |
| 最小（手动指定Skill） | 0 | 1 | 3 | 4 |

## 6. Prompt 设计

三个阶段各一个 Prompt 类，遵循项目既有 `@dataclass(frozen=True)` 模式：

| Prompt | 角色 | 输入 | 输出 |
|--------|------|------|------|
| `SkillSelectionPrompt` | 测试架构师 | 业务知识 + 需求 + Skill 目录 | `["boundary_value", ...]` |
| `TestPointGenerationPrompt` | 测试工程师 | 业务知识 + 需求 + 批次规则 | `[{id, skill, title, ...}]` |
| `TestCaseExpansionPrompt` | 测试工程师 | 业务知识 + 需求 + 测试点 + 展开规则 + 风格参考 | `[{id, title, type, steps, ...}]` |

## 7. 关键技术决策

### 7.1 为什么 Phase 1 按批次而非逐 Skill 调用？

逐 Skill 调用质量更高（LLM 每次只关注一个维度），但 6 次调用延迟太长。3 组批次在质量和延迟间取平衡——同批 Skill 语义相近（如边界+异常都关注输入侧），LLM 可以同时处理。

### 7.2 为什么 Phase 2 分片展开？

实测 49+ 测试点一次性展开，8192 max_tokens 仍会截断。按 15 个一批分片后每批都能完整输出，最后合并。每批有独立 try/except，单批失败不丢失其他数据。

### 7.3 为什么保留旧 TestCaseAgent？

新 Agent 调用 5~9 次 LLM，P50 延迟约 30~50 秒。旧 Agent 仅 1 次调用，适合快速生成场景。关键词路由中将"用例"/"测试"等全部指向新 Agent，旧 Agent 仅通过 `app="testcase"` 显式调用。

### 7.4 为什么需求文档不通过检索获取？

检索会丢失内容。需求文档定义测试范围，必须全部保留。用 `split_documents(chunk_size=800)` 分片后全部拼接，利用 DeepSeek 128K 上下文承载。

## 8. 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `AiLearning/skills/skill_definition.py` | 新建 | Skill dataclass + 6 个内置 Skill + 批次分组 + 辅助函数 |
| `AiLearning/skills/__init__.py` | 新建 | 注册表导出 |
| `AiLearning/prompts/testcase_design.py` | 新建 | 3 个 Prompt 类（frozen dataclass） |
| `AiLearning/agents/testcase_design_agent.py` | 新建 | Agent 实现（~180 行） |
| `AiLearning/rag/vector_store.py` | 修改 | 新增 `get_by_filename()` |
| `AiLearning/router/agent_router.py` | 修改 | 注册 + 关键词优先级列表（list of tuples） |
| `AiLearning/prompts/router.py` | 修改 | 意图检测增加 `testcase_design` 标签 |
| `main.py` | 修改 | `AskRequest` 增加 `requirement_doc` 和 `reference_case_filenames` |
| `AiLearning/agents/__init__.py` | 修改 | 导出 |
| `AiLearning/prompts/__init__.py` | 修改 | 导出 |
