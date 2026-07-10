import json
from dataclasses import dataclass


@dataclass(frozen=True)
class SkillSelectionPrompt:
    """Phase 0：测试架构师基于业务知识和需求选择适用测试维度。"""

    system: str = (
        "你是一个测试架构师，深入掌握该业务领域。"
        "你已经阅读了业务领域知识和需求文档，现在需要判断从哪些测试维度进行用例设计。"
    )

    template: str = (
        "## 业务领域知识（你已掌握的背景）\n"
        "{context}\n\n"
        "## 新需求\n"
        "{requirement}\n\n"
        "## 可选测试维度\n"
        "{skills_catalog}\n\n"
        "用户需求：{question}\n\n"
        "要求：\n"
        "1. 根据业务知识中的规则、约束、风险点，判断哪些测试维度确实适用于本次需求\n"
        "2. 返回 JSON 数组，包含选中的 skill 的 name 字段\n"
        '3. 格式示例：["boundary_value", "permission_security"]\n'
        "4. 只输出 JSON 数组，不要包含其他文字"
    )

    template_with_model: str = (
        "## 业务规则（已建模的领域知识）\n"
        "{model_rules}\n\n"
        "## 新需求\n"
        "{requirement}\n\n"
        "## 可选测试维度\n"
        "{skills_catalog}\n\n"
        "用户需求：{question}\n\n"
        "要求：\n"
        "1. 每条业务规则标注了 related_skill，以此为参考判断哪些维度适用于新需求\n"
        "2. 返回 JSON 数组，包含选中的 skill 的 name 字段\n"
        '3. 格式示例：["boundary_value", "permission_security"]\n'
        "4. 只输出 JSON 数组，不要包含其他文字"
    )

    def format(self, context: str, requirement: str, question: str, skills_catalog: str) -> str:
        return self.template.format(
            context=context,
            requirement=requirement,
            question=question,
            skills_catalog=skills_catalog,
        )

    def format_with_model(self, model_rules: str, requirement: str, question: str,
                          skills_catalog: str) -> str:
        """用业务模型的 rules 替代 RAG context 进行 Skill 选择。"""
        return self.template_with_model.format(
            model_rules=model_rules,
            requirement=requirement,
            question=question,
            skills_catalog=skills_catalog,
        )


@dataclass(frozen=True)
class TestPointGenerationPrompt:
    """Phase 1：基于领域知识，按批次Skill的规则生成测试点。"""

    system: str = (
        "你是一个资深测试工程师，深入掌握该业务领域的知识、规则和历史缺陷。"
        "你擅长运用业务理解，针对新需求从不同测试维度设计精准的测试点。"
    )

    template: str = (
        "## 业务领域知识（你已掌握的背景）\n"
        "{context}\n\n"
        "## 新需求文档\n"
        "{requirement}\n\n"
        "## 当前批次测试维度\n"
        "批次名称：{group_name}\n"
        "各维度测试点生成规则：\n"
        "{batch_rules}\n\n"
        "要求：\n"
        "1. 为批次中的每个测试维度分别生成测试点\n"
        "2. 业务知识中的规则、逻辑和约束是新需求必须遵守的，根据这些知识识别具体的测试条件\n"
        "3. 每个测试点是一个 JSON 对象，包含以下字段：\n"
        "   - id: 测试点编号（如 TP-001）\n"
        "   - skill: 所属技能名称\n"
        "   - title: 简短标题（15字以内）\n"
        "   - description: 测试目标和关键条件（50字以内）\n"
        "   - related_context: 引用的具体业务规则、风险点或文档段落\n"
        "4. 测试点应具体、可执行，不应笼统\n"
        "5. 只输出 JSON 数组，不要包含其他文字"
    )

    def format(self, context: str, requirement: str, group_name: str, batch_rules: str) -> str:
        return self.template.format(
            context=context,
            requirement=requirement,
            group_name=group_name,
            batch_rules=batch_rules,
        )


@dataclass(frozen=True)
class TestCaseExpansionPrompt:
    """Phase 2：将测试点展开为完整用例，结合参考用例的风格。"""

    system: str = (
        "你是一个资深测试工程师，擅长将测试点展开为完整、可执行的测试用例。"
        "你注重用例的结构规范、步骤可操作性和预期结果的可验证性。"
    )

    template: str = (
        "## 业务领域知识\n"
        "{context}\n\n"
        "## 新需求文档\n"
        "{requirement}\n\n"
        "## 测试点列表\n"
        "{test_points}\n\n"
        "## 用例展开规则\n"
        "{case_rules}\n\n"
        "## 参考用例（风格参考）\n"
        "{reference_cases}\n\n"
        "要求：\n"
        "1. 将每个测试点展开为完整的测试用例，遵守对应的展开规则\n"
        "2. 每条用例包含以下字段：\n"
        "   - id: 用例编号（如 TC-001）\n"
        "   - title: 用例标题\n"
        "   - type: 用例类型（对应测试维度的 display_name）\n"
        "   - precondition: 前置条件\n"
        "   - steps: 测试步骤列表\n"
        "   - expected: 预期结果\n"
        "3. 参考用例仅用于学习命名风格、步骤细化程度和预期结果描述句式，"
        "用一致的风格编写新用例\n"
        "4. 只输出 JSON 数组，不要包含其他文字"
    )

    def format(self, context: str, requirement: str, test_points: str,
               case_rules: str, reference_cases: str = "") -> str:
        return self.template.format(
            context=context,
            requirement=requirement,
            test_points=test_points,
            case_rules=case_rules,
            reference_cases=reference_cases or "无参考用例",
        )


@dataclass(frozen=True)
class ImpactAnalysisPrompt:
    """Phase -0.5：基于已有业务模型，分析新需求影响哪些业务模块和回归范围。"""

    system: str = (
        "你是一个资深的测试架构师，擅长评估需求变更对已有业务模型的影响范围。"
        "\n\n"
        "已知一个知识库（KB）的业务模型代表当前系统的业务全貌，"
        "分析「新传入的需求文档」会影响哪些业务模块。"
        "\n\n"
        "核心原则：\n"
        "- KB 的业务模型是确定的，代表当前系统完整业务\n"
        "- 新需求文档可能只描述增量变更，不会重复完整业务描述\n"
        '- 只输出新需求中确实提到的变更点，不推测"可能"存在的变更\n'
        "- 与已有模型一致的内容不算变更"
        "\n\n"
        "分析逻辑：\n"
        "1. 逐条提取新需求文档中的变更（阈值调整、新增字段、新增约束、流程变化等）\n"
        "2. 对每条变更，判断影响哪个已有实体/流程/规则\n"
        "3. 根据变更点推导需要回归的测试模块\n"
        "4. 如果新需求与已有模型完全无差异，no_impact=true"
        "\n\n"
        "输出要求：\n"
        "- 只输出 JSON，不要有任何解释或 markdown 包裹"
    )

    template: str = (
        "## 已有业务模型（此 KB 的业务全貌）\n"
        "```json\n"
        "{previous_model}\n"
        "```\n\n"
        "## 新需求文档（本次传入，可能只描述变更部分）\n"
        "{current_requirement}\n\n"
        "请输出变更影响分析 JSON（不要 markdown 包裹）："
    )

    def format(self, previous_model: str, current_requirement: str) -> str:
        return self.template.format(
            previous_model=previous_model,
            current_requirement=current_requirement,
        )


# 默认实例（供 Agent 直接使用）
DEFAULT_SKILL_SELECTION_PROMPT = SkillSelectionPrompt()
DEFAULT_TESTPOINT_PROMPT = TestPointGenerationPrompt()
DEFAULT_EXPANSION_PROMPT = TestCaseExpansionPrompt()
DEFAULT_IMPACT_ANALYSIS_PROMPT = ImpactAnalysisPrompt()
