"""业务建模 + 影响范围评估数据结构。

业务建模阶段从需求文档中提取实体、流程、状态、规则四层模型，
结合领域特征（资金/权限/数据/内容），为后续 Skill 选择提供结构化上下文。
影响范围评估阶段分析变更涉及的组件、未变更模块和回归范围。
"""

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum


# ═══════════════════════════════════════════════════════════════════════
# 领域类型枚举
# ═══════════════════════════════════════════════════════════════════════

class DomainType(str, Enum):
    finance = "finance"         # 资金流转、结算、对账
    permission = "permission"   # RBAC、多租户隔离
    data = "data"               # 报表、看板、数据管道
    content = "content"         # UGC、内容审核、发布生命周期
    general = "general"         # 不落入特定领域，通用四层即可覆盖


# ═══════════════════════════════════════════════════════════════════════
# 通用四层模型
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class EntityModel:
    """业务实体及其属性和约束。"""
    name: str
    attributes: list[str]
    key_constraints: list[str]


@dataclass(frozen=True)
class FlowModel:
    """业务流程，包含步骤和分支条件。"""
    name: str
    steps: list[str]
    branch_conditions: list[str]


@dataclass(frozen=True)
class StateModel:
    """实体状态机，包含所有状态转换及风险点。"""
    entity: str
    transitions: list[dict]   # [{from, to, trigger, risk}, ...]


@dataclass(frozen=True)
class RuleModel:
    """业务规则，关联到对应测试维度。"""
    name: str
    condition: str
    risk: str
    related_skill: str        # Skill 注册名，如 "state_machine" / "boundary_value"
    source_quote: str = ""    # 原文引用，用于追溯规则来源，防止 LLM 编造


# ═══════════════════════════════════════════════════════════════════════
# 领域扩展模型
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class MoneyModel:
    """资金领域：资金流转路径和风险点。"""
    money_flows: list[str]
    risk_points: list[str]


@dataclass(frozen=True)
class PermModel:
    """权限领域：角色、权限矩阵和隔离边界。"""
    roles: list[str]
    permission_matrix: list[dict]   # [{role, resource, action}, ...]
    isolation_boundaries: list[str]


@dataclass(frozen=True)
class DataModel:
    """数据领域：数据源、聚合逻辑和一致性要求。"""
    data_sources: list[str]
    aggregations: list[str]
    consistency_requirements: list[str]


@dataclass(frozen=True)
class ContentModel:
    """内容领域：内容类型和审核策略。"""
    content_types: list[str]
    audit_strategies: list[str]


# ═══════════════════════════════════════════════════════════════════════
# 聚合模型
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class BusinessModel:
    """完整的业务模型，聚合通用四层 + 领域扩展。"""
    entities: list[EntityModel]
    flows: list[FlowModel]
    states: list[StateModel]
    rules: list[RuleModel]
    domain_type: DomainType
    domain_model: MoneyModel | PermModel | DataModel | ContentModel | None


@dataclass(frozen=True)
class RequirementDiff:
    """需求文档层面的单条变更点。"""
    type: str              # threshold / field_add / field_required / text / other
    description: str
    old_value: str | None
    new_value: str | None
    affected_scope: list[str]


@dataclass(frozen=True)
class ImpactAnalysis:
    """需求变更影响范围评估。

    基于已有业务模型，分析新需求文档影响的业务模块和回归范围。
    no_impact 为 True 时表示无需回归。
    """
    requirement_diffs: list[RequirementDiff]
    regression_scope: list[str]           # 受影响的业务模块名称
    regression_focus: list[str] = ()      # 受影响规则对应 related_skill 的去重集合
    no_impact: bool = False


# ═══════════════════════════════════════════════════════════════════════
# 上下文
# ═══════════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class ModelingContext:
    """Phase -0.5 所需的上下文参数。

    API 层组装此对象，Agent 内部统一取值。
    enabled=False 时完全跳过，与现有流程一致。
    """
    enabled: bool = False
    previous_model: dict | None = None
    previous_requirement: str = ""


# ═══════════════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════════════

def model_to_dict(obj):
    """将 BusinessModel / dataclass 递归转为纯 dict，用于 JSON 序列化。"""
    if obj is None:
        return None
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: model_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [model_to_dict(i) for i in obj]
    if is_dataclass(obj):
        return {k: model_to_dict(v) for k, v in asdict(obj).items()}
    return obj


DOMAIN_TYPE_MAP: dict[DomainType, type] = {
    DomainType.finance: MoneyModel,
    DomainType.permission: PermModel,
    DomainType.data: DataModel,
    DomainType.content: ContentModel,
}
