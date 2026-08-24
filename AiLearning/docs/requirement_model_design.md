# 需求模型设计（M2-1 定稿 v2）

`parse_requirement` 的产物：把一篇 PRD 解析成结构化需求模型，供下游做节点级维度选择、场景用例串联、覆盖率追溯。

## 设计决策

1. **三层结构**：流程（Flow）→ 任务（Task）→ 规则（Rule）。字段/逻辑约束全部下沉到 Rule；Flow 级只保留入口/资格类校验（preconditions）。
2. **全链路 ID**：`F1` → `F1.T2` → `F1.T2.R3`。覆盖率统计、用例↔需求点追溯、badcase 定位都建立在 ID 上。
3. **场景串联靠 produces**：任务间粘合剂是"A 的产出 = B 的前置"，所以 Task 必须有 `produces`（执行后改变的状态/数据），配合 `relations` 和 `data_dependencies`。
4. **缺失三段式**（agent 无人值守，不能靠"问用户"卡流程）：
   - 能解析的 → 正常解析；
   - 缺失但可推断的 → 模型补齐并标 `assumed: true`（下游对假设项降权/标注）；
   - 关键且不可推断的 → 进顶层 `open_questions`，生成照常，结果附带问题清单。
5. **规则 = 条件 → 预期**：Rule 必有 `condition` + `expected`，否则下游生成用例的预期结果就是模型现编的，可评测性归零。
6. **模型保持纯净**：schema 只装"需求事实"，不放 `suggested_dimensions` 之类设计决策——维度选择是下游独立步骤（parse ≠ design）。
7. **任务类型是维度证据**：`type`（录入/审批/同步/计算/通知/其他）直接喂给维度选择的证据标准（如同步类 → data_consistency）。

## JSON Schema

机器可读版见 `AiLearning/capabilities/schemas/requirement_model.schema.json`，结构如下：

```
RequirementModel
├── title: string
├── summary: string                      # 需求一句话概述
├── flows: Flow[]
│   ├── id: "F1"
│   ├── name: string
│   ├── description: string
│   ├── preconditions: string[]          # 入口/资格校验（能不能进这个流程）
│   ├── relations: [{ type: mutex|depends_on|sequence, target: "F2" }]
│   ├── assumed: bool (default false)
│   └── tasks: Task[]
│       ├── id: "F1.T1"
│       ├── name: string
│       ├── type: string                 # 录入/审批/同步/计算/通知/其他
│       ├── description: string          # 任务具体内容
│       ├── scenarios: string[]          # 不同的任务提交场景
│       ├── relations: [{ type: depends_on|sequence|mutex, target: "F1.T2" }]
│       ├── data_dependencies: string[]  # 读写的数据/表/外部接口
│       ├── produces: string[]           # 后置状态/产出（场景串联的粘合剂）
│       ├── assumed: bool (default false)
│       └── rules: Rule[]
│           ├── id: "F1.T1.R1"
│           ├── description: string
│           ├── condition: string        # 什么情况下
│           ├── expected: string         # 应该发生什么
│           └── assumed: bool (default false)
└── open_questions: string[]             # 关键且不可推断的缺失，附带给用户
```

## 示例（缩略，商户增店）

```json
{
  "title": "商户增店流程优化",
  "summary": "存量商户新增门店，复用公司信息，需审核后生效",
  "flows": [{
    "id": "F1", "name": "增店申请",
    "preconditions": ["商户状态为合作中", "商户无进行中的增店流程"],
    "relations": [{"type": "mutex", "target": "F2"}],
    "tasks": [{
      "id": "F1.T1", "name": "提交增店申请", "type": "录入",
      "scenarios": ["单店新增", "批量新增"],
      "relations": [{"type": "sequence", "target": "F1.T2"}],
      "data_dependencies": ["商户表", "门店表"],
      "produces": ["待审核的增店申请单"],
      "rules": [{
        "id": "F1.T1.R1",
        "condition": "同一商户下门店名称",
        "expected": "不允许重复，重复时拒绝并提示已存在的门店",
        "assumed": false
      }]
    }]
  }],
  "open_questions": ["批量新增的单次上限数量未在文档中说明"]
}
```

## 消费方式（M2-2/M2-3 的接口约定）

- LLM 侧：structured output / JSON mode 约束输出，pydantic 校验，校验失败带错误信息重试
- 下游：维度选择遍历 Task（证据 = type + description + rules），场景生成按 relations + produces 串路径
- 覆盖率：以 Rule.id 为最小统计单元
