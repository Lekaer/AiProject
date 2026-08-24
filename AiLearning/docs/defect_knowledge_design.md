# 缺陷知识库设计（M3-1 定稿 v2）

把"系统以前怎么挂的"固化为 AI 可检索的资产，供用例生成时按任务自动召回。
评审结论（用户 draft + review 修正）：缺关联维度字段与 ID、召回键方向修正（现象/模块是匹配面，根因是负载）、根因与问题类型合并、腐化用最简方案。

## 记录 schema（一条缺陷 = 一条记录 = 一个 chunk）

```
id: DEF-001                    # 稳定 ID，用例可标注"源自 DEF-001"形成证据链
title: 缺陷标题
phenomenon: 现象描述            # 现象先行！"提交后状态未更新"，不是根因先行——写法决定召回率
service: 服务名
module: 模块名                  # 匹配面：与需求模型 Task 的数据依赖/模块词汇对齐
root_cause: 根因（枚举，可生长） # 负载而非召回键——生成时恰恰不知道根因
dimension: 关联测试维度         # 6 个 skill 之一；召回后直接作为维度选择的证据
fix: 修复方式（可选）           # 对人读有用，对生成价值低
status: active | archived      # 腐化控制：模块重构/下线时批量标 archived
recorded_at: YYYY-MM-DD
```

**root_cause 起始枚举**（录数据时允许生长，新类型先入枚举再录入）：
缓存未失效 / 并发竞争 / 边界未校验 / 状态流转遗漏 / 第三方依赖未兜底 / 数据精度 / 配置遗漏 / 空值未处理

## 检索组织

- **chunk 文本** = title + phenomenon + service + module + root_cause 拼接（一条缺陷一个 chunk，故事完整性优先）
- **metadata** = id / dimension / status，查询侧过滤 `status=active`
- 独立 collection（如 `defects`），与现有 `testcase` 知识库分开

## 查询构造（架构决策：从可选工具 → 管线确定性步骤）

- 生成时查询词**不由模型自由发挥**：pipeline 逐任务用结构化字段程序构造——
  `query = 流程名 + 任务名 + 任务类型 + 数据依赖`；可按数据依赖拆多路窄查询，合并去重
- 命中结果直接注入该任务的生成 prompt 上下文（"历史缺陷优先覆盖"从 prompt 愿望变成结构保证）
- `rag_search` 工具保留，降级为模型的临时补查手段
- 全面性 = 遍历结构保证（每个任务必查）；准确性 = 度量收口（金标准"任务↔缺陷"关联对算 hit rate，M3-1d）

## 腐化与清理（最简方案，不过度设计）

- 字段只要 `status` + `recorded_at`
- 唯一规则：模块重构/下线时，该模块记录批量标 archived（不删除、检索排除）
- 不做定期 review 流程——库的规模配不上

## 数据文件格式

`data/defects/defects.jsonl`，每行一条记录（字段同 schema）。灌库脚本读 JSONL → 拼 chunk 文本 → 写向量库 + BM25 索引。
