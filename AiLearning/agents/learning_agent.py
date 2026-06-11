from AiLearning.agents.base import AgentResponse, BaseAgent
from AiLearning.prompts.learning import DEFAULT_LEARNING_PROMPT
from AiLearning.rag.retriever import retrieve
from AiLearning.service import get_client


class LearningAgent(BaseAgent):
    """学习助手 Agent。

    以通俗易懂的方式解释概念，使用类比和例子帮助理解。
    temperature 设为 0.7，略高于默认值：
    - 学习场景不要求逐字忠于原文，允许不同角度重新组织解释
    - 类比和举例本身有一定随机性，略高的温度能产生更多样的例子
    - 0.7 仍在可控范围内，不会偏离知识点
    """

    @property
    def name(self) -> str:
        return "learning"

    def execute(self, question: str, **kwargs) -> AgentResponse:
        collection_name = kwargs.get("collection_name")

        context_docs = retrieve(question, collection_name) if collection_name else []
        context = self._build_context(context_docs)

        prompt = DEFAULT_LEARNING_PROMPT.format(context=context, question=question)

        answer = get_client().chat(
            messages=[
                {"role": "system", "content": DEFAULT_LEARNING_PROMPT.system},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )

        return AgentResponse(
            answer=answer,
            agent_name=self.name,
            metadata={"retrieved_docs": len(context_docs), "temperature": 0.7},
        )
