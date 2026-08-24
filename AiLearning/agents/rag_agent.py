from AiLearning.agents.base import AgentResponse, BaseAgent
from AiLearning.prompts.rag import DEFAULT_RAG_PROMPT
from AiLearning.rag.retriever import retrieve, retrieve_from_multiple_collections
from AiLearning.service import get_client


class RAGAgent(BaseAgent):
    """通用 RAG 问答 Agent。

    检索知识库中与问题最相关的文档片段，拼接为上下文后由 LLM 回答。
    """

    @property
    def name(self) -> str:
        return "rag"

    def execute(self, question: str, **kwargs) -> AgentResponse:
        collection_names = kwargs.get("collection_names", [])
        collection_name = kwargs.get("collection_name")

        if collection_names:
            print(collection_names)
            context_docs = retrieve_from_multiple_collections(question, collection_names)
        elif collection_name:
            print(collection_name)
            context_docs = retrieve(question, collection_name)
        else:
            context_docs = []

        context = self._build_context(context_docs)

        prompt = DEFAULT_RAG_PROMPT.format(context=context, question=question)

        answer = get_client().chat(
            messages=[
                {"role": "system", "content": DEFAULT_RAG_PROMPT.system},
                {"role": "user", "content": prompt},
            ],
        )

        return AgentResponse(
            answer=answer,
            agent_name=self.name,
            metadata={"retrieved_docs": len(context_docs)},
        )
