import logging
import time as time_module
from typing import Iterator

import openai
from openai import OpenAI

logger = logging.getLogger(__name__)


class AIError(Exception):
    """AI 客户端统一异常，包装各类 OpenAI SDK 错误。"""

    def __init__(self, message: str, original_error: Exception | None = None):
        super().__init__(message)
        self.original_error = original_error


class AIClient:
    """OpenAI 兼容 SDK 的轻量封装。

    提供对话补全（流式/非流式）和 embedding 生成能力。
    不依赖 Django，所有配置通过构造函数传入。
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        default_model: str = "deepseek-v4-pro",
        timeout: float = 60.0,
    ):
        self.default_model = default_model
        # max_retries=2: SDK 内部重试，避免网络抖动导致失败
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=2,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        reasoning_effort: str | None = None,
        extra_body: dict | None = None,
        **kwargs,
    ) -> str:
        """发送非流式对话请求，返回完整回复文本。"""
        try:
            response = self._client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                stream=False,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                extra_body=extra_body,
                **kwargs,
            )
            return response.choices[0].message.content or ""
        except openai.AuthenticationError as e:
            raise AIError(f"Authentication failed: {e}", original_error=e) from e
        except openai.RateLimitError as e:
            raise AIError(f"Rate limit exceeded: {e}", original_error=e) from e
        except openai.APIConnectionError as e:
            raise AIError(f"Network error: {e}", original_error=e) from e
        except openai.APITimeoutError as e:
            raise AIError(f"Request timed out: {e}", original_error=e) from e
        except openai.APIError as e:
            status = getattr(e, "status_code", "?")
            raise AIError(f"API error (status {status}): {e}", original_error=e) from e
        except Exception as e:
            logger.exception("Unexpected error during chat completion")
            raise AIError(f"Unexpected error: {e}", original_error=e) from e

    def chat_with_usage(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        reasoning_effort: str | None = None,
        extra_body: dict | None = None,
        **kwargs,
    ) -> tuple[str, dict, float]:
        """非流式对话 + token 用量 + 耗时。

        Returns:
            (content, usage_dict, elapsed_seconds)
            usage_dict = {"prompt_tokens", "completion_tokens", "total_tokens"}
        """
        start = time_module.perf_counter()
        try:
            response = self._client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                stream=False,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                extra_body=extra_body,
                **kwargs,
            )
            elapsed = time_module.perf_counter() - start
            content = response.choices[0].message.content or ""
            usage = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens or 0,
                    "completion_tokens": response.usage.completion_tokens or 0,
                    "total_tokens": response.usage.total_tokens or 0,
                }
            return content, usage, elapsed
        except openai.AuthenticationError as e:
            raise AIError(f"Authentication failed: {e}", original_error=e) from e
        except openai.RateLimitError as e:
            raise AIError(f"Rate limit exceeded: {e}", original_error=e) from e
        except openai.APIConnectionError as e:
            raise AIError(f"Network error: {e}", original_error=e) from e
        except openai.APITimeoutError as e:
            raise AIError(f"Request timed out: {e}", original_error=e) from e
        except openai.APIError as e:
            status = getattr(e, "status_code", "?")
            raise AIError(f"API error (status {status}): {e}", original_error=e) from e
        except Exception as e:
            logger.exception("Unexpected error during chat completion")
            raise AIError(f"Unexpected error: {e}", original_error=e) from e

    def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        reasoning_effort: str | None = None,
        extra_body: dict | None = None,
        **kwargs,
    ) -> Iterator[str]:
        """流式对话补全，逐步 yield 文本块。"""
        try:
            stream = self._client.chat.completions.create(
                model=model or self.default_model,
                messages=messages,
                stream=True,
                temperature=temperature,
                max_tokens=max_tokens,
                reasoning_effort=reasoning_effort,
                extra_body=extra_body,
                **kwargs,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
        except openai.AuthenticationError as e:
            raise AIError(f"Authentication failed: {e}", original_error=e) from e
        except openai.RateLimitError as e:
            raise AIError(f"Rate limit exceeded: {e}", original_error=e) from e
        except openai.APIConnectionError as e:
            raise AIError(f"Network error: {e}", original_error=e) from e
        except openai.APITimeoutError as e:
            raise AIError(f"Request timed out: {e}", original_error=e) from e
        except openai.APIError as e:
            status = getattr(e, "status_code", "?")
            raise AIError(f"API error (status {status}): {e}", original_error=e) from e
        except Exception as e:
            logger.exception("Unexpected error during streaming chat")
            raise AIError(f"Unexpected error: {e}", original_error=e) from e

    def embed(
        self,
        text: str,
        model: str = "text-embedding-ada-002",
        **kwargs,
    ) -> list[float]:
        """为单个文本生成 embedding 向量。"""
        try:
            response = self._client.embeddings.create(
                input=[text],
                model=model,
                **kwargs,
            )
            return response.data[0].embedding
        except openai.AuthenticationError as e:
            raise AIError(f"Authentication failed: {e}", original_error=e) from e
        except openai.RateLimitError as e:
            raise AIError(f"Rate limit exceeded: {e}", original_error=e) from e
        except openai.APIConnectionError as e:
            raise AIError(f"Network error: {e}", original_error=e) from e
        except openai.APITimeoutError as e:
            raise AIError(f"Request timed out: {e}", original_error=e) from e
        except openai.APIError as e:
            status = getattr(e, "status_code", "?")
            raise AIError(f"API error (status {status}): {e}", original_error=e) from e
        except Exception as e:
            logger.exception("Unexpected error during embedding")
            raise AIError(f"Unexpected error: {e}", original_error=e) from e

    def embed_batch(
        self,
        texts: list[str],
        model: str = "text-embedding-ada-002",
        **kwargs,
    ) -> list[list[float]]:
        """为多条文本批量生成 embedding 向量。"""
        try:
            response = self._client.embeddings.create(
                input=texts,
                model=model,
                **kwargs,
            )
            return [d.embedding for d in response.data]
        except openai.AuthenticationError as e:
            raise AIError(f"Authentication failed: {e}", original_error=e) from e
        except openai.RateLimitError as e:
            raise AIError(f"Rate limit exceeded: {e}", original_error=e) from e
        except openai.APIConnectionError as e:
            raise AIError(f"Network error: {e}", original_error=e) from e
        except openai.APITimeoutError as e:
            raise AIError(f"Request timed out: {e}", original_error=e) from e
        except openai.APIError as e:
            status = getattr(e, "status_code", "?")
            raise AIError(f"API error (status {status}): {e}", original_error=e) from e
        except Exception as e:
            logger.exception("Unexpected error during batch embedding")
            raise AIError(f"Unexpected error: {e}", original_error=e) from e


# AI 客户端模块级单例
_client: AIClient | None = None


def get_client() -> AIClient:
    """获取模块级 AIClient 单例，从 config.py + 环境变量读取配置。"""
    global _client
    if _client is None:
        from config import (
            DEEPSEEK_API_KEY,
            DEEPSEEK_BASE_URL,
            DEEPSEEK_MODEL,
            DEEPSEEK_TIMEOUT,
        )

        _client = AIClient(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            default_model=DEEPSEEK_MODEL,
            timeout=DEEPSEEK_TIMEOUT,
        )
    return _client


from AiLearning.prompts.rag import DEFAULT_RAG_PROMPT


def generate(question: str, context_docs: list[str]) -> str:
    """根据问题和检索到的上下文文档生成回答。"""
    context = "\n\n".join(context_docs) if context_docs else "无相关上下文信息"
    prompt = DEFAULT_RAG_PROMPT.format(context=context, question=question)
    return get_client().chat(
        messages=[
            {"role": "system", "content": DEFAULT_RAG_PROMPT.system},
            {"role": "user", "content": prompt},
        ],
    )
