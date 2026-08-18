"""parse_requirement：把 PRD 文档解析成结构化需求模型（M2-2）。

流程：读文档文本 → LLM（JSON mode, temperature=0）→ pydantic 校验
→ 失败时把错误信息反馈给模型重试（默认最多 2 次）。

设计依据：AiLearning/docs/requirement_model_design.md（M2-1 v2）。
长文档当前整篇喂入（PRD 一般几千字，可接受）；若后续遇到超大文档，
在 load_document 与 LLM 调用之间加分块 map-reduce 即可，接口不变。
"""

import json
import os

from pydantic import ValidationError

from AiLearning.capabilities.requirement_model import RequirementModel
from AiLearning.harness.llm import default_model, get_client

SYSTEM_PROMPT = """你是资深需求分析师，负责把需求文档解析成结构化需求模型（JSON）。

# 输出结构（严格遵守）
{
  "title": "需求标题",
  "summary": "一句话概述",
  "flows": [{
    "id": "F1", "name": "流程名", "description": "流程说明",
    "preconditions": ["入口/资格类校验（能不能进这个流程）"],
    "relations": [{"type": "mutex|depends_on|sequence", "target": "F2"}],
    "assumed": false,
    "tasks": [{
      "id": "F1.T1", "name": "任务名",
      "type": "录入|审批|同步|计算|通知|其他",
      "description": "任务具体内容",
      "scenarios": ["不同的任务提交场景"],
      "relations": [{"type": "depends_on|sequence|mutex", "target": "F1.T2"}],
      "data_dependencies": ["读写的数据/表/外部接口"],
      "produces": ["执行后产出的状态/数据（供下游任务消费）"],
      "assumed": false, "change": "new",
      "rules": [{
        "id": "F1.T1.R1", "description": "规则说明",
        "condition": "什么情况下", "expected": "应该发生什么",
        "assumed": false, "change": "new"
      }]
    }]
  }],
  "open_questions": ["关键且无法从文档推断的缺失信息"]
}

# 解析规则
1. 层级：流程（Flow）→ 任务（Task）→ 规则（Rule）。字段/逻辑约束全部放到 Rule；Flow 的 preconditions 只放入口/资格类校验。
2. ID 规则：流程 F1、F2…；任务 F1.T1、F1.T2…；规则 F1.T1.R1…。必须全局唯一，relations 的 target 必须指向存在的 ID。
3. Rule 必须拆成 condition（什么情况下）和 expected（应该发生什么），这是硬要求。
4. 缺失处理三段式：
   - 文档明确写的 → 正常解析；
   - 文档没写但可合理推断的 → 补齐，并把该节点的 assumed 标为 true；
   - 关键且无法推断的 → 不要编造，写进 open_questions。
5. 只输出 JSON，不要输出任何解释文字。
6. 变更标记（change）：如果文档是优化/改造类需求（在既有功能上修改），必须为每个任务和规则标注 change：new（本次新增）/ modified（本次修改）/ unchanged_affected（未修改但因共享数据、接口或流程而受牵连）。全新需求的全部标 new。判断为 modified 或 unchanged_affected 时要谨慎，只标有明确依据的。"""

class ParseError(Exception):
    def __init__(self, attempt: int, last_error: Exception):
        self.attempt = attempt
        self.last_error = last_error
        super().__init__(f"解析重试 {attempt} 次后仍失败：{last_error}")


def load_document(source: str) -> str:
    """读取文档文本。source 是存在的文件路径时读文件（txt/md 直读，pdf 用 pypdf），
    否则把 source 本身当需求文本。"""
    if not os.path.exists(source):
        return source
    ext = os.path.splitext(source)[1].lower()
    if ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(source)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    with open(source, encoding="utf-8") as f:
        return f.read()


def parse_requirement(
    source: str,
    max_retries: int = 2,
    max_tokens: int = 16000,
    model: str | None = None,
) -> RequirementModel:
    """把 PRD（文件路径或文本）解析为 RequirementModel。

    校验失败（JSON 不合法或不符合模型）时，把错误信息追加进对话让模型修正，
    最多重试 max_retries 次；仍失败则抛 ValidationError。
    """
    text = load_document(source)
    client = get_client()
    model = model or default_model()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"请解析以下需求文档：\n\n{text}"},
    ]

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 2):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,  # 解析任务要求确定性
            max_tokens=max_tokens,
        )
        raw = response.choices[0].message.content or ""
        try:
            return RequirementModel.model_validate(json.loads(raw))
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = e
            # 把模型的原始输出和校验错误一起喂回去，让它基于错误修正
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": f"上一条输出未通过校验，错误：{e}\n请修正后重新输出完整 JSON。",
            })
    raise ParseError(max_retries, last_error)
