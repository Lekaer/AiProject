"""离线业务建模 Agent，从领域文档中提取结构化 BusinessModel。"""

import json
import logging
import re

from AiLearning.agents.base import AgentResponse, BaseAgent
from AiLearning.service import get_client

logger = logging.getLogger(__name__)


MODELING_SYSTEM = (
    "你是一个资深的业务架构师，擅长从需求文档和技术文档中提取结构化的业务模型。"
    "你需要仔细阅读文档，识别其中的业务实体、流程、状态机和规则，并判断所属的业务领域。"
    "\n\n"
    "核心原则：\n"
    "- 只提取文档中明确描述的内容，不推测、不补充、不编造\n"
    "- 不要将数据库表名、技术中间件（Redis/Kafka/MongoDB）作为业务实体\n"
    '- 相似的变体合并为一个实体（如"品质保证金账户"和"品牌保证金账户"统一为"资金账户"）'
    "\n\n"
    "输出要求：\n"
    "- 只输出 JSON，不要有任何解释或 markdown 包裹\n"
    "- 严格遵循给定的 JSON Schema\n"
    "- entities：核心业务实体（不是数据库表、不是技术组件）。每个实体列 3-6 个关键业务属性，"
    "不要逐字段罗列数据库列名。相同业务概念下的变体合并为一个实体。\n"
    "- flows：主要业务流程（≤8 个），不要展开子流程和异常分支。每个流程列 3-7 个核心步骤。\n"
    "- states：列出文档中有状态流转的实体（通常1-3个），每个列出核心转换路径（3-5 条）。没有则不填。\n"
    "- rules：列出文档中所有明确的业务规则和约束条件。每条规则必须附带 source_quote 字段，"
    "从原文中引用原句，无法找到原文支撑的规则不要输出。"
    "\n\n"
    "输出 JSON Schema：\n"
    '{\n'
    '  "domain_type": "finance|permission|data|content|general",\n'
    '  "entities": [{"name": "实体名", "attributes": ["属性1", "属性2"], "key_constraints": ["约束1"]}],\n'
    '  "flows": [{"name": "流程名", "steps": ["步骤1", "步骤2"], "branch_conditions": ["条件1"]}],\n'
    '  "states": [{"entity": "实体名", "transitions": [{"from": "待处理", "to": "处理中", "trigger": "提交", "risk": "低风险"}]}],\n'
    '  "rules": [{"name": "规则名", "condition": "触发条件", "risk": "违反风险", '
    '"related_skill": "boundary_value|exception_path|permission_security|state_machine|data_consistency|combinatorial", '
    '"source_quote": "原文中直接支撑该规则的原句"}],\n'
    '  "domain_model": null\n'
    '}'
)

MODELING_USER = (
    "请从以下领域文档中提取业务模型。\n\n"
    "## 领域文档\n"
    "{documents_text}\n\n"
    "请输出 JSON（不要 markdown 包裹）："
)


class ModelingAgent(BaseAgent):
    """离线业务建模 Agent。"""

    @property
    def name(self) -> str:
        return "modeling"

    def execute(self, question: str, **kwargs) -> AgentResponse:
        raise NotImplementedError("use build_model() instead")

    def build_model(self, documents: list[str]) -> dict:
        """从文档文本列表中提取业务模型。

        Args:
            documents: 每篇文档的完整文本内容。

        Returns:
            业务模型 dict（BusinessModel 结构）。
        """
        documents_text = "\n\n---\n\n".join(
            f"## 文档 {i+1}\n{doc}" for i, doc in enumerate(documents)
        )

        client = get_client()
        messages = [
            {"role": "system", "content": MODELING_SYSTEM},
            {"role": "user", "content": MODELING_USER.format(documents_text=documents_text)},
        ]

        response, usage, elapsed = client.chat_with_usage(
            messages=messages,
            temperature=0,
            max_tokens=8192,
        )
        logger.info(
            "[modeling] elapsed=%.1fs tokens(in=%d out=%d total=%d)",
            elapsed,
            usage.get("prompt_tokens", 0),
            usage.get("completion_tokens", 0),
            usage.get("total_tokens", 0),
        )

        model = _parse_json_dict(response)
        self._check_source_quotes(model)
        return model

    @staticmethod
    def _check_source_quotes(model: dict):
        """轻量校验：检查规则是否有原文引用支持，缺失过多时告警。"""
        rules = model.get("rules", [])
        if not rules:
            return
        missing = [r.get("name", "?") for r in rules if not r.get("source_quote", "").strip()]
        if missing:
            ratio = len(missing) / len(rules)
            if ratio >= 0.5:
                logger.warning("建模结果中 %d/%d 条规则缺少 source_quote（>=50%%），"
                               "可能存在编造: %s", len(missing), len(rules), missing)
            else:
                logger.info("建模结果中 %d/%d 条规则缺少 source_quote: %s",
                            len(missing), len(rules), missing)


def _parse_json_dict(raw: str) -> dict:
    """3 层 fallback 解析 LLM 输出的 JSON 对象。"""
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    logger.warning("无法从 LLM 响应中解析 JSON 对象: %s", text[:200])
    return {}
