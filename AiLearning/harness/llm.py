"""harness 级 LLM 客户端工厂。

OpenAI 兼容客户端单例，配置全部来自环境变量（见 config.py）。
loop 和 capability 的确定性调用（如 parse_requirement）共用此入口，
避免客户端配置（timeout/重试）多处漂移。
"""

from openai import OpenAI

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_TIMEOUT

        _client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=DEEPSEEK_TIMEOUT,
            max_retries=2,
        )
    return _client


def default_model() -> str:
    from config import DEEPSEEK_MODEL

    return DEEPSEEK_MODEL
