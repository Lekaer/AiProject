import logging
from typing import Generator

from AiLearning.agents.base import AgentResponse
from AiLearning.agents.learning_agent import LearningAgent
from AiLearning.agents.rag_agent import RAGAgent
from AiLearning.agents.testcase_agent import TestCaseAgent
from AiLearning.agents.testcase_design_agent import TestCaseDesignAgent
from AiLearning.prompts.router import INTENT_DETECTION_PROMPT
from AiLearning.service import get_client

logger = logging.getLogger(__name__)

# ── agent 注册表 ────────────────────────────────────────────────────

_agents: dict[str, "BaseAgent"] = {}


def _init_registry():
    """懒加载注册内置 agent，幂等。"""
    if _agents:
        return
    for agent_cls in (RAGAgent, TestCaseAgent, LearningAgent, TestCaseDesignAgent):
        instance = agent_cls()
        _agents[instance.name] = instance


def _get_agent(name: str):
    """按名称查找 agent，不存在返回 None。"""
    _init_registry()
    return _agents.get(name)


# ── 关键词映射 ──────────────────────────────────────────────────────

_KEYWORD_MAP: list[tuple[str, list[str]]] = [
    ("testcase_design", ["用例", "测试", "case", "test", "需求", "设计用例", "用例设计", "补充"]),
    ("learning", ["解释", "学习", "计划", "路线", "实践"]),
]


def _keyword_detect(question: str) -> str | None:
    """按优先级扫描问题中的关键词，命中则返回 agent 名称，无命中返回 None。"""
    q_lower = question.lower()
    for agent_name, keywords in _KEYWORD_MAP:
        for kw in keywords:
            if kw.lower() in q_lower:
                return agent_name
    return None


# ── LLM 意图识别 ────────────────────────────────────────────────────

def _llm_detect_intent(question: str) -> str:
    """调用 LLM 判断意图，失败或结果未知时 fallback 到 rag。"""
    try:
        prompt = INTENT_DETECTION_PROMPT.format(question=question)
        label = get_client().chat(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10,
            temperature=0,
        )
        label = label.strip().lower()
        if label in _agents:
            return label
        logger.warning("LLM returned unknown intent: %r, fallback to rag", label)
        return "rag"
    except Exception:
        logger.exception("Intent detection failed, fallback to rag")
        return "rag"


# ── 公共 API ────────────────────────────────────────────────────────

def dispatch(question: str, app: str | None, **kwargs) -> AgentResponse:
    """三级意图解析：app 显式指定 → 关键词匹配 → LLM 意图识别（fallback: rag）。

    所有额外参数（如 collection_name）透传给 Agent，router 不关心 Agent 需要什么。

    Raises:
        ValueError: app 指定的 agent 不存在。
    """
    _init_registry()

    # 第一级：app 参数显式指定
    if app:
        agent = _get_agent(app)
        if agent is None:
            available = sorted(_agents.keys())
            raise ValueError(f"Unknown agent: {app!r}. Available: {available}")
        return agent.execute(question, **kwargs)

    # 第二级：关键词匹配
    agent_name = _keyword_detect(question)
    if agent_name:
        agent = _get_agent(agent_name)
        if agent:
            return agent.execute(question, **kwargs)

    # 第三级：LLM 意图识别
    agent_name = _llm_detect_intent(question)
    agent = _get_agent(agent_name)
    if agent is None:
        agent = _get_agent("rag")
    return agent.execute(question, **kwargs)


def dispatch_stream(question: str, app: str | None,
                    cancelled=None, **kwargs) -> Generator[dict, None, None]:
    """SSE streaming 版 dispatch，路由逻辑同 dispatch()，但 yield 进度事件。

    路由到 agent.execute_stream()（如 TestCaseDesignAgent）。若 agent 不支持
    streaming，则降级为 execute() + 单次 done 事件。
    """
    _init_registry()

    # 三级路由（同 dispatch）
    if app:
        agent = _get_agent(app)
        if agent is None:
            yield {"event": "error", "data": {"message": f"Unknown agent: {app!r}"}}
            return
    else:
        agent_name = _keyword_detect(question)
        if agent_name:
            agent = _get_agent(agent_name)
        else:
            agent_name = _llm_detect_intent(question)
            agent = _get_agent(agent_name)
        if agent is None:
            agent = _get_agent("rag")

    # 调用 streaming 或降级
    stream_method = getattr(agent, "execute_stream", None)
    if stream_method:
        yield from stream_method(question, cancelled=cancelled, **kwargs)
    else:
        try:
            result = agent.execute(question, **kwargs)
            yield {
                "event": "done",
                "data": {
                    "answer": result.answer,
                    "metadata": result.metadata,
                },
            }
        except Exception as e:
            yield {"event": "error", "data": {"message": str(e)}}


def registered_agents() -> list[str]:
    """返回所有已注册 agent 的名称列表。"""
    _init_registry()
    return sorted(_agents.keys())


if __name__ == '__main__':

    question = "解释一下什么是回归测试"
    collection = "col_aaf01d1195d17942"
    result = dispatch(question, app=None)
    print(f"[{result.agent_name}] {result.answer}")