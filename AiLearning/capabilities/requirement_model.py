"""需求模型的 pydantic 定义（M2-1 schema 的代码侧镜像）。

与 capabilities/schemas/requirement_model.schema.json 保持一致：
- 三层 Flow → Task → Rule，全链路 ID（F1 / F1.T2 / F1.T2.R3）
- Rule 强制 condition + expected
- assumed / open_questions 承载缺失三段式
- 额外做 schema 做不到的两条交叉校验：ID 全局唯一、relations 的 target 必须存在
"""

import re

from pydantic import BaseModel, Field, model_validator, field_validator
from sqlalchemy import literal
from typing import Literal

FLOW_ID = re.compile(r"^F[0-9]+$")
TASK_ID = re.compile(r"^F[0-9]+\.T[0-9]+$")
RULE_ID = re.compile(r"^F[0-9]+\.T[0-9]+\.R[0-9]+$")


class FlowRelation(BaseModel):
    type: str = Field(pattern="^(mutex|depends_on|sequence)$")
    target: str = Field(pattern=FLOW_ID.pattern)


class TaskRelation(BaseModel):
    type: str = Field(pattern="^(depends_on|sequence|mutex)$")
    target: str = Field(pattern=TASK_ID.pattern)


class Rule(BaseModel):
    id: str = Field(pattern=RULE_ID.pattern)
    description: str = ""
    condition: str = Field(min_length=1)
    expected: str = Field(min_length=1)
    assumed: bool = False
    change: Literal["new", "modified", "unchanged_affected"] = "new"
    # 变更标记（M3-3）：优化类需求解析时标注本条规则是 新增/修改/未变但受影响；
    # modified 和 unchanged_affected 是 regression 维度选择的证据


class Task(BaseModel):
    id: str = Field(pattern=TASK_ID.pattern)
    name: str
    type: str  # 录入/审批/同步/计算/通知/其他；维度选择的证据之一
    description: str
    scenarios: list[str] = Field(default_factory=list)
    relations: list[TaskRelation] = Field(default_factory=list)
    data_dependencies: list[str] = Field(default_factory=list)
    produces: list[str] = Field(default_factory=list)
    assumed: bool = False
    change: Literal["new", "modified", "unchanged_affected"] = "new"
    rules: list[Rule] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def check_name_not_blank(cls, v):
        if not v:
            raise ValueError("name不能是空白")
        return v



class Flow(BaseModel):
    id: str = Field(pattern=FLOW_ID.pattern)
    name: str
    description: str = ""
    preconditions: list[str] = Field(default_factory=list)
    relations: list[FlowRelation] = Field(default_factory=list)
    assumed: bool = False
    tasks: list[Task] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def check_name_not_blank(cls, v):
        if not v:
            raise ValueError("name不能是空白")
        return v


class RequirementModel(BaseModel):
    title: str
    summary: str
    flows: list[Flow]
    open_questions: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_ids_unique_and_targets_exist(self) -> "RequirementModel":
        flow_ids = [f.id for f in self.flows]
        task_ids = [t.id for f in self.flows for t in f.tasks]
        rule_ids = [r.id for f in self.flows for t in f.tasks for r in t.rules]

        for label, ids in (("flow", flow_ids), ("task", task_ids), ("rule", rule_ids)):
            dup = {i for i in ids if ids.count(i) > 1}
            if dup:
                raise ValueError(f"{label} id 重复: {sorted(dup)}")

        flow_set, task_set = set(flow_ids), set(task_ids)
        for f in self.flows:
            for rel in f.relations:
                if rel.target not in flow_set:
                    raise ValueError(f"{f.id} 的 relation 指向不存在的 flow: {rel.target}")
            for t in f.tasks:
                for rel in t.relations:
                    if rel.target not in task_set:
                        raise ValueError(f"{t.id} 的 relation 指向不存在的 task: {rel.target}")
        return self

    def stats(self) -> dict:
        """供覆盖率/日志用的概要统计。"""
        tasks = [t for f in self.flows for t in f.tasks]
        rules = self.all_rules
        return {
            "flows": len(self.flows),
            "tasks": len(tasks),
            "rules": len(rules),
            "assumed": sum(
                f.assumed for f in self.flows
            ) + sum(t.assumed for t in tasks) + sum(r.assumed for r in rules),
            "open_questions": len(self.open_questions),
        }

    @property
    def all_rules(self):
        tasks = [t for f in self.flows for t in f.tasks]
        rules = [r for t in tasks for r in t.rules]
        return rules

