from dataclasses import dataclass


@dataclass(frozen=True)
class LearningPrompt:
    """学习助手提示词。

    角色定位为耐心、善于用类比解释概念的学习导师。
    temperature 设为 0.7（高于 RAG 问答的默认值 0.0）：
    - 学习场景不需要逐字忠实于原文，允许模型用不同角度重新组织解释
    - 类比和举例本身带有一定随机性，略高的温度能产生更多样的例子
    - 0.7 仍在可控范围内，不会让回答偏离知识点
    """

    system: str = (
        "你是一个耐心、知识渊博的学习助手。你擅长用通俗易懂的语言解释复杂概念，"
        "善用类比和生活中的例子帮助学习者建立直觉理解。"
    )

    template: str = (
        "请根据以下参考材料，帮助学习者理解相关概念。\n\n"
        "参考材料：\n{context}\n\n"
        "学习者的问题：{question}\n\n"
        "要求：\n"
        "1. 用通俗易懂的语言解释核心概念\n"
        "2. 至少使用一个生活中的类比帮助理解\n"
        "3. 如果参考材料不足以解释清楚，可以用你自己的知识补充，并标注哪些是补充内容\n"
        "4. 结构清晰，逐步深入"
    )

    def format(self, context: str, question: str) -> str:
        """将上下文和问题填入模板。"""
        return self.template.format(context=context, question=question)


DEFAULT_LEARNING_PROMPT = LearningPrompt()
