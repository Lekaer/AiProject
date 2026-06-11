from AiLearning.agents.base import AgentResponse, BaseAgent
from AiLearning.prompts.testcase import DEFAULT_TESTCASE_PROMPT
from AiLearning.rag.retriever import retrieve
from AiLearning.service import get_client


class TestCaseAgent(BaseAgent):
    """测试用例生成 Agent。

    检索知识库中的需求文档，生成覆盖正常流程、边界值、异常场景和权限校验的用例。
    检索 top_k 设为 8（比通用问答的默认 5 更大），因为测试用例需要更完整的上下文覆盖。
    """

    @property
    def name(self) -> str:
        return "testcase"

    def execute(self, question: str, **kwargs) -> AgentResponse:
        collection_name = kwargs.get("collection_name")

        context_docs = retrieve(question, collection_name, top_k=8) if collection_name else []
        context = self._build_context(context_docs)

        prompt = DEFAULT_TESTCASE_PROMPT.format(context=context, question=question)

        answer = get_client().chat(
            messages=[
                {"role": "system", "content": DEFAULT_TESTCASE_PROMPT.system},
                {"role": "user", "content": prompt},
            ],
        )

        return AgentResponse(
            answer=answer,
            agent_name=self.name,
            metadata={"retrieved_docs": len(context_docs), "top_k": 8},
        )
