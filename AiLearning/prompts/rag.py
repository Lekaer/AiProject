from dataclasses import dataclass


@dataclass(frozen=True)
class RAGPrompt:
    """通用 RAG 问答提示词。

    迁移自 rag/generator.py 中的 PROMPT_TEMPLATE，增加了 system 角色字段，
    使 LLM 在对话中先建立角色认知，再执行具体问答。
    """

    system: str = "你是一个知识问答助手，请根据提供的上下文准确回答用户问题。如果上下文中没有相关信息，请如实说明。"

    template: str = (
        "你是一个知识问答助手，请根据以下上下文回答用户问题。\n"
        "上下文：{context}\n"
        "问题：{question}\n"
        "请给出准确简洁的回答。"
    )

    def format(self, context: str, question: str) -> str:
        """将上下文和问题填入模板，返回完整的用户消息。"""
        return self.template.format(context=context, question=question)


DEFAULT_RAG_PROMPT = RAGPrompt()
