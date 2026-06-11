from dataclasses import dataclass


@dataclass(frozen=True)
class TestCasePrompt:
    """测试用例生成提示词。

    以测试工程师角色驱动 LLM，要求输出结构化的测试用例列表。
    覆盖正常流程、边界值、异常场景和权限校验四类用例。
    """

    system: str = (
        "你是一个资深测试工程师，擅长根据需求文档和接口规范设计全面的测试用例。"
        "你注重边界条件、异常路径和权限安全，输出结构清晰、可直接执行。"
    )

    template: str = (
        "请根据以下文档内容，生成完整的测试用例集合。\n\n"
        "参考文档：\n{context}\n\n"
        "测试需求：{question}\n\n"
        "要求：\n"
        "1. 覆盖正常流程、边界值、异常场景、权限校验四类用例\n"
        "2. 每条用例包含以下字段：\n"
        "   - id: 用例编号（如 TC-001）\n"
        "   - title: 用例标题\n"
        "   - type: 用例类型（正常流程 / 边界值 / 异常场景 / 权限校验）\n"
        "   - precondition: 前置条件\n"
        "   - steps: 测试步骤列表\n"
        "   - expected: 预期结果\n"
        "3. 只输出 JSON 数组，不要包含其他文字\n"
        '4. 格式：[{{"id": "TC-001", "title": "...", "type": "正常流程", '
        '"precondition": "...", "steps": ["步骤1", "步骤2"], "expected": "..."}}]'
    )

    def format(self, context: str, question: str) -> str:
        """将上下文和测试需求填入模板。"""
        return self.template.format(context=context, question=question)


DEFAULT_TESTCASE_PROMPT = TestCasePrompt()
