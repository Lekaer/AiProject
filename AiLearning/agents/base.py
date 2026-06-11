from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResponse:
    """Agent 执行结果的统一封装。

    Attributes:
        answer: LLM 生成的回答文本。
        agent_name: 执行该请求的 agent 标识（如 "rag", "testcase"）。
        metadata: 附加信息（如检索到的文档数量、参数等），便于调试和日志。
    """

    answer: str
    agent_name: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Agent 抽象基类。

    每个 Agent 封装一种"用 RAG 做什么事"的完整逻辑：
    检索 → 组装 prompt → 调用 LLM → 返回结果。

    execute() 接受 **kwargs，允许不同 Agent 按需声明自己的参数，
    不强制所有 Agent 都依赖检索。
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent 唯一标识，用作 API `app` 参数和意图路由。"""
        ...

    @abstractmethod
    def execute(self, question: str, **kwargs: Any) -> AgentResponse:
        ...

    def _build_context(self, context_docs: list[str]) -> str:
        """将检索到的文档列表拼接为 prompt 可用的上下文字符串。"""
        return "\n\n".join(context_docs) if context_docs else "无相关上下文信息"
