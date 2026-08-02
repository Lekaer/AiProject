from dataclasses import dataclass


@dataclass(frozen=True)
class RequirementVariationPrompt:
    """数据合成：基于种子需求衍生多样化变体。"""

    system: str = (
        "你是一个资深测试需求分析师，深入掌握支付、资金、财务系统的业务流程和业务规则。"
        "你擅长从已有需求文档中提取核心业务模式和约束条件，并衍生出多样化、合理的变化场景，"
        "用于构建高质量的测试用例设计训练数据集。"
    )

    template: str = (
        "## 种子需求\n"
        "{seed_text}\n\n"
        "## 指令\n"
        "基于上述种子需求的核心业务模式（订单取消、资金收款、支付异常等），"
        "衍生 {target_count} 条不同的需求变体。每条变体包含完整的业务需求文档。\n\n"
        "变化维度要求：\n"
        "1. 变化资金类型：保证金 → 服务费 → 意向金 → 违约金 → 保底费 等\n"
        "2. 变化业务场景：入驻 → 合同变更 → 续签 → 换签 → 退网 → 减店 → 增店\n"
        "3. 变化复杂度：单订单 → 父子订单 → 批量订单\n"
        "4. 变化约束条件：金额门槛、分期规则、权限角色、时间窗口\n"
        "5. 变化异常场景：支付超时/部分支付/金额不匹配/消息丢失/并发冲突\n\n"
        "要求：\n"
        "1. 每条变体的需求文档应完整、具体，包含明确的业务规则和约束条件\n"
        "2. 变体之间应保持业务模式一致（资金/支付/订单领域），但场景和参数显著不同\n"
        "3. 每条需求文档 200-600 字\n"
        "4. 返回 JSON 数组：[\n"
        '  {{"requirement_doc": "完整需求描述", '
        '"skill": "state_machine|data_consistency|exception_path", '
        '"difficulty": "easy|medium|hard"}}\n'
        "]\n"
        "5. skill 应与种子需求对应，表示该需求最适合的测试维度\n"
        "6. 只输出 JSON 数组，不要包含其他文字"
    )

    def format(self, seed_text: str, target_count: int) -> str:
        return self.template.format(seed_text=seed_text, target_count=target_count)


@dataclass(frozen=True)
class QualityScoringPrompt:
    """数据合成：LLM-as-Judge 质量评分。"""

    system: str = (
        "你是一个严格的测试用例质量评估专家。你精通软件测试方法论，"
        "从多个维度客观评估测试用例的质量，不因测试用例外观美观而放松标准。"
    )

    template: str = (
        "## 待评分样本\n"
        "{samples_json}\n\n"
        "## 评分维度\n"
        "对每条样本的三个维度分别评分（1-5 分）：\n\n"
        "- faithfulness（忠实度）：用例是否准确反映了需求描述的业务规则和约束条件。"
        "5分=完全反映所有规则，3分=部分反映，1分=与需求无关或错误。\n"
        "- completeness（完整度）：用例是否覆盖了需求中描述的主要场景和边界条件。"
        "5分=全面覆盖，3分=覆盖主要场景但遗漏边界，1分=严重遗漏。\n"
        "- executability（可执行性）：测试步骤是否具体、可操作，能由测试人员直接执行。"
        "5分=每步可直接执行，3分=部分步骤需额外解释，1分=模糊不可执行。\n\n"
        "输出格式：[\n"
        '  {{"index": 0, "faithfulness": 4, "completeness": 4, '
        '"executability": 5, "reason": "一句话评价"}}\n'
        "]\n"
        "只输出 JSON 数组，不要包含其他文字。"
    )

    def format(self, samples_json: str) -> str:
        return self.template.format(samples_json=samples_json)


DEFAULT_VARIATION_PROMPT = RequirementVariationPrompt()
DEFAULT_QUALITY_SCORING_PROMPT = QualityScoringPrompt()
