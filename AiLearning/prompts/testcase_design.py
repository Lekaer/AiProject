import json
from dataclasses import dataclass


@dataclass(frozen=True)
class SkillSelectionPrompt:
    """Phase 0：测试架构师基于业务知识和需求选择适用测试维度。"""

    system: str = (
        "你是一个测试架构师，深入掌握该业务领域。"
        "你已经阅读了业务知识文档和技术需求文档，现在需要判断从哪些测试维度进行用例设计。"
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

    def format(self, context: str, requirement: str, question: str, skills_catalog: str) -> str:
        return self.template.format(
            context=context,
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


# 默认实例（供 Agent 直接使用）
DEFAULT_SKILL_SELECTION_PROMPT = SkillSelectionPrompt()
DEFAULT_TESTPOINT_PROMPT = TestPointGenerationPrompt()
DEFAULT_EXPANSION_PROMPT = TestCaseExpansionPrompt()
