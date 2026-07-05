from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    """测试维度技能，定义测试点生成规则和用例展开规则。"""

    name: str              # 唯一标识，如 "boundary_value"
    display_name: str      # 中文名，如 "边界值分析"
    description: str       # 一句话说明
    test_point_rules: str  # Phase 1: 测试点生成规则
    test_case_rules: str   # Phase 2: 用例展开规则


# ═══════════════════════════════════════════════════════════════════════
# 6 个内置 Skill
# ═══════════════════════════════════════════════════════════════════════

SKILL_BOUNDARY_VALUE = Skill(
    name="boundary_value",
    display_name="边界值分析",
    description="数值边界、日期范围、字符串长度、集合大小的边界测试",
    test_point_rules=(
        "识别需求文档和业务规则中所有涉及数值、日期、字符串、集合的输入和参数。"
        "对每个参数生成以下测试点：\n"
        "- 最小边界值（如最小值、最早日期、空字符串、空集合）\n"
        "- 最大边界值（如最大值、最晚日期、最大长度、最大数量）\n"
        "- 边界+1（超出上限）和边界-1（低于下限）\n"
        "- 零值、负值（如适用）\n"
        "结合业务知识：业务规则中提到的限额、阈值、周期等应作为边界值测试的重点。"
    ),
    test_case_rules=(
        "对每个边界测试点，展开为完整用例：\n"
        "- 前置条件必须明确设定边界场景（如当前值为阈值-1）\n"
        "- 测试步骤中写明具体输入值和验证方式\n"
        "- 预期结果须明确：接受并正确处理 / 拒绝并给出具体错误码 / 系统稳定不崩溃"
    ),
)

SKILL_EXCEPTION_PATH = Skill(
    name="exception_path",
    display_name="异常路径",
    description="非法输入、网络故障、依赖服务异常、并发冲突等异常场景",
    test_point_rules=(
        "识别需求文档中依赖的外部系统、用户输入点、并发操作场景。"
        "对每个风险点生成以下测试点：\n"
        "- 输入异常：null值、格式错误、类型不匹配、超长内容、特殊字符注入\n"
        "- 依赖异常：下游服务超时、返回异常、不可达\n"
        "- 并发异常：同一资源同时操作、重复提交\n"
        "- 资源异常：存储满、内存溢出、连接池耗尽\n"
        "结合业务知识：历史缺陷中提到的异常场景和故障记录应优先覆盖。"
    ),
    test_case_rules=(
        "对每个异常测试点，展开为完整用例：\n"
        "- 前置条件描述正常环境配置和触发异常的特定条件\n"
        "- 测试步骤中先建立正常状态，再触发异常\n"
        "- 预期结果明确：系统返回具体错误码、不影响其他业务、有合理日志记录"
    ),
)

SKILL_PERMISSION_SECURITY = Skill(
    name="permission_security",
    display_name="权限安全",
    description="认证、授权、角色权限、跨租户隔离、敏感数据保护",
    test_point_rules=(
        "识别需求文档中涉及的用户角色、权限控制点、敏感数据。"
        "对每个权限边界生成以下测试点：\n"
        "- 未认证访问：不携带token/携带无效token访问\n"
        "- 角色越权：低权限角色尝试高权限操作\n"
        "- 跨租户隔离：租户A尝试访问租户B的数据\n"
        "- token安全：过期token、被篡改token、不同用户token\n"
        "- 敏感数据：响应中是否泄露密码/密钥、日志中是否脱敏\n"
        "结合业务知识：业务规则中定义的权限模型和审批流程是设计权限用例的基础。"
    ),
    test_case_rules=(
        "对每个权限测试点，展开为完整用例：\n"
        "- 前置条件中明确当前用户角色、权限状态、所属租户\n"
        "- 测试步骤中详细写出请求头、参数和认证凭据\n"
        "- 预期结果明确：返回403/401、数据隔离正常、无敏感信息泄露"
    ),
)

SKILL_STATE_MACHINE = Skill(
    name="state_machine",
    display_name="状态机覆盖",
    description="实体生命周期中所有合法/非法状态转换、幂等、并发状态更新",
    test_point_rules=(
        "识别需求文档中具有状态流转的实体（如订单、工单、申请单）。"
        "梳理完整的状态机图后，生成以下测试点：\n"
        "- 每个合法状态转换路径（正向流程）\n"
        "- 每个非法状态转换（如从终态退回中间态）\n"
        "- 重复执行同一状态变更（幂等性）\n"
        "- 并发状态变更（两个请求同时改状态）\n"
        "- 状态变更后的回滚/撤销\n"
        "结合业务知识：业务规则中定义的状态流转规则是设计状态机用例的唯一依据。"
    ),
    test_case_rules=(
        "对每个状态机测试点，展开为完整用例：\n"
        "- 前置条件明确当前状态和触发操作\n"
        "- 测试步骤中先设置初始状态，再执行状态变更操作\n"
        "- 预期结果明确：状态变更成功/被拒绝、数据一致、幂等操作无副作用"
    ),
)

SKILL_DATA_CONSISTENCY = Skill(
    name="data_consistency",
    display_name="数据一致性",
    description="事务完整性、重复提交、缓存一致性、级联更新",
    test_point_rules=(
        "识别需求文档中涉及数据库操作、缓存使用、多表关联的场景。"
        "对每个数据操作点生成以下测试点：\n"
        "- 事务回滚：操作链中间失败，前置操作是否正确回滚\n"
        "- 幂等性：相同请求重复发送（如用户双击提交）\n"
        "- 缓存一致性：数据更新后缓存是否同步失效/更新\n"
        "- 读写一致性：写后立即查，读到的是否为最新数据\n"
        "- 级联操作：主表删除后关联表是否正确处理\n"
        "结合业务知识：业务规则中的数据校验逻辑和关联关系是数据一致性测试的基础。"
    ),
    test_case_rules=(
        "对每个数据一致性测试点，展开为完整用例：\n"
        "- 前置条件中准备好初始数据和关联数据\n"
        "- 测试步骤中模拟失败点（如断网、超时）并观察数据状态\n"
        "- 预期结果明确：数据要么全部成功要么全部回滚，无中间状态"
    ),
)

SKILL_COMBINATORIAL = Skill(
    name="combinatorial",
    display_name="组合场景",
    description="跨模块交互、多参数组合、多条件叠加、端到端完整流程",
    test_point_rules=(
        "识别需求文档中涉及多个功能模块、可选参数、条件分支的场景。"
        "生成以下组合测试点：\n"
        "- 多参数正交组合（至少覆盖关键参数的 pairwise 组合）\n"
        "- 跨模块串联：A模块输出作为B模块输入的全链路\n"
        "- 条件叠加：多个优惠/折扣/规则同时生效\n"
        "- 正常+异常混合：前置步骤正常、中间步骤异常的场景\n"
        "结合业务知识：业务规则中的约束条件和历史缺陷中的薄弱模块是组合测试的重点。"
    ),
    test_case_rules=(
        "对每个组合测试点，展开为完整用例：\n"
        "- 前置条件中列出所有参与模块的初始状态\n"
        "- 测试步骤按时间顺序描述跨模块交互\n"
        "- 预期结果明确每个模块的行为和最终业务结果"
    ),
)

# ═══════════════════════════════════════════════════════════════════════
# Skill 注册表
# ═══════════════════════════════════════════════════════════════════════

SKILL_REGISTRY: dict[str, Skill] = {
    "boundary_value": SKILL_BOUNDARY_VALUE,
    "exception_path": SKILL_EXCEPTION_PATH,
    "permission_security": SKILL_PERMISSION_SECURITY,
    "state_machine": SKILL_STATE_MACHINE,
    "data_consistency": SKILL_DATA_CONSISTENCY,
    "combinatorial": SKILL_COMBINATORIAL,
}

# ═══════════════════════════════════════════════════════════════════════
# 批次分组：相近 Skill 合并为一次 LLM 调用
# ═══════════════════════════════════════════════════════════════════════

SKILL_BATCHES = [
    {
        "group_name": "边界与异常",
        "skills": ["boundary_value", "exception_path"],
    },
    {
        "group_name": "权限与状态",
        "skills": ["permission_security", "state_machine"],
    },
    {
        "group_name": "数据与组合",
        "skills": ["data_consistency", "combinatorial"],
    },
]


def build_skills_catalog() -> str:
    """生成供 LLM 选择的技能目录文本。"""
    lines = []
    for skill in SKILL_REGISTRY.values():
        lines.append(f"- {skill.name}（{skill.display_name}）：{skill.description}")
    return "\n".join(lines)


def get_skills_by_names(names: list[str]) -> list[Skill]:
    """按名称获取 Skill 列表，忽略不存在的名称。"""
    return [SKILL_REGISTRY[n] for n in names if n in SKILL_REGISTRY]
