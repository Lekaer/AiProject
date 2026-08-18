"""工具注册表 + harness 通用工具。

ToolRegistry 是通用机制：name -> (JSON schema, handler)，loop 只依赖这个接口，
不关心具体有哪些工具。任何 capability 都可以往注册表里挂自己的工具。

harness 只保留与具体 capability 无关的通用工具：
- rag_search   : 调 RAG 混合检索，返回命中文本片段；无索引/失败时优雅降级
- write_output : 把最终产物写入 outputs/（路径沙箱化，禁止目录穿越）

capability 专属工具（如 load_skill）在 capabilities/tools.py 注册，
由 capability 自己把通用工具和专属工具组合成完整注册表。
"""

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass

# 输出目录（仓库根 outputs/），write_output 的沙箱根
OUTPUTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "outputs",
)


@dataclass
class Tool:
    """一个可被 LLM 调用的工具。"""

    name: str                 # 工具名，LLM 通过它发起调用
    description: str          # 给 LLM 看的说明（决定模型何时用、怎么用）
    parameters: dict          # JSON Schema（OpenAI tools 格式的 parameters 段）
    handler: Callable[..., str]  # 实际执行函数，入参为 kwargs，返回字符串结果


class ToolRegistry:
    """工具注册表：负责 schema 导出和按名分发执行。"""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict]:
        """导出 OpenAI chat.completions 的 tools 参数格式。"""
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in self._tools.values()
        ]

    def execute(self, name: str, args: dict) -> str:
        """按名执行工具；未知工具或执行异常都转成字符串结果返回给模型。"""
        tool = self._tools.get(name)
        if tool is None:
            return f"错误：未知工具 '{name}'，可用工具：{sorted(self._tools)}"
        try:
            return tool.handler(**args)
        except TypeError as e:
            return f"错误：工具参数不合法（{e}），期望参数 schema：{json.dumps(tool.parameters, ensure_ascii=False)}"
        except Exception as e:
            return f"错误：工具执行失败（{type(e).__name__}: {e}）"

    def tool(self, name: str, description: str, parameters: dict):
        def decorator(func):
            self.register(Tool(name=name, description=description, parameters=parameters, handler=func))
            return func
        return decorator

# ═══════════════════════════════════════════════════════════════════════
# M1 三个内置工具的 handler
# ═══════════════════════════════════════════════════════════════════════


def _rag_search(query: str) -> str:
    """混合检索（向量 + BM25 + RRF），返回命中文本片段；失败时优雅降级。"""
    try:
        from AiLearning.rag import retriever

        # 目前可用的知识库集合写死为 testcase（用例设计相关知识）；
        # 索引不存在或 embedding 模型不可用时 retriever 会抛异常，走降级分支
        docs = retriever.retrieve(query, collection_name="testcase", top_k=5)
    except Exception as e:
        return f"检索不可用（{type(e).__name__}: {e}），返回空结果。请基于需求本身继续设计用例。"
    if not docs:
        return "未检索到相关内容（空结果）。请基于需求本身继续设计用例。"
    return "\n\n---\n\n".join(
        f"[片段 {i + 1} | 来源: testcase 知识库]\n{doc}" for i, doc in enumerate(docs)
    )


def _write_output(filename: str, content: str) -> str:
    """写入 outputs/ 目录；解析后的绝对路径必须落在 outputs/ 内（防目录穿越）。"""
    outputs_root = os.path.realpath(OUTPUTS_DIR)
    target = os.path.realpath(os.path.join(outputs_root, filename))
    if target != outputs_root and not target.startswith(outputs_root + os.sep):
        return f"错误：非法文件名 '{filename}'，只能写入 outputs/ 目录内"
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return f"已写入 {target}（{len(content.encode('utf-8'))} 字节）"


def build_generic_registry() -> ToolRegistry:
    """构建 harness 通用工具集：rag_search + write_output。

    capability 专属工具由 capabilities/tools.py 在此之上追加。
    """
    registry = ToolRegistry()
    # registry.register(Tool(
    #     name="rag_search",
    #     description="检索测试设计相关知识库（历史用例、业务规则、缺陷记录）。当需求描述缺少业务上下文时使用。",
    #     parameters={
    #         "type": "object",
    #         "properties": {
    #             "query": {"type": "string", "description": "检索关键词或问题"},
    #         },
    #         "required": ["query"],
    #     },
    #     handler=_rag_search,
    # ))
    @registry.tool(
        name="rag_search",
        description="检索测试设计相关知识库（历史用例、业务规则、缺陷记录）。当需求描述缺少业务上下文时使用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "检索关键词或问题"},
            },
            "required": ["query"],
        }
    )
    def _rag_search(query: str) -> str:
        """混合检索（向量 + BM25 + RRF），返回命中文本片段；失败时优雅降级。"""
        try:
            from AiLearning.rag import retriever

            # 目前可用的知识库集合写死为 testcase（用例设计相关知识）；
            # 索引不存在或 embedding 模型不可用时 retriever 会抛异常，走降级分支
            docs = retriever.retrieve(query, collection_name="testcase", top_k=5)
        except Exception as e:
            return f"检索不可用（{type(e).__name__}: {e}），返回空结果。请基于需求本身继续设计用例。"
        if not docs:
            return "未检索到相关内容（空结果）。请基于需求本身继续设计用例。"
        return "\n\n---\n\n".join(
            f"[片段 {i + 1} | 来源: testcase 知识库]\n{doc}" for i, doc in enumerate(docs)
        )
    registry.register(Tool(
        name="write_output",
        description="把最终生成的测试用例写入 outputs/ 目录。内容必须是 JSON 数组，每个元素含 title/precondition/steps/expected 四个字段。",
        parameters={
            "type": "object",
            "properties": {
                "filename": {"type": "string", "description": "文件名（相对 outputs/），如 coupon_cases.json"},
                "content": {"type": "string", "description": "文件内容（JSON 数组字符串）"},
            },
            "required": ["filename", "content"],
        },
        handler=_write_output,
    ))
    return registry
