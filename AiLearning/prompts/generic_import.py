from dataclasses import dataclass


@dataclass(frozen=True)
class GenericImportPrompt:
    """从任意格式文档中提取测试用例，统一转换为标准结构。"""

    system: str = (
        "你是一个测试用例标准化专家。你的任务是从任意格式的测试文档中"
        "识别并提取所有测试用例，统一转换为标准结构。"
        "如果文档中没有明确的测试用例，请根据文档中的场景、流程和功能点自行归纳组织。"
    )

    template: str = (
        "## 原始文档\n"
        "{document}\n\n"
        "要求：\n"
        "1. 从上述文档中提取所有测试用例，不足 1 条时根据内容合理组织\n"
        "2. 每条用例包含：id、title、type、precondition、steps、expected\n"
        "3. id 如未明确编号则自动生成 TC-001，type 根据内容推断（如功能测试/边界值测试/异常测试/状态机测试等）\n"
        "4. steps 为字符串数组，每个步骤一句话\n"
        "5. 只输出 JSON 数组，不要包含其他文字\n"
        '6. 格式：[{{"id": "TC-001", "title": "...", "type": "功能测试", "precondition": "...", "steps": ["步骤1", "步骤2"], "expected": "..."}}]'
    )

    def format(self, document: str) -> str:
        return self.template.format(document=document)


DEFAULT_GENERIC_IMPORT_PROMPT = GenericImportPrompt()
