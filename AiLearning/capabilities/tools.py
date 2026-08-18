"""capability 专属工具：与测试用例设计能力绑定的工具注册。

harness/tools.py 只放通用工具（rag_search、write_output）；
本文件放依赖用例生成领域知识的工具（load_skill 依赖 SKILL_REGISTRY），
并提供组合好的完整注册表供 capability 使用。
"""

from AiLearning.harness.tools import Tool, ToolRegistry, build_generic_registry


def _load_skill(name: str) -> str:
    """按 name 加载技能：返回对应 SKILL.md 的正文全文（何时使用/生成规则/展开规则/反例）。"""
    from AiLearning.skills.skill_definition import SKILL_REGISTRY

    skill = SKILL_REGISTRY.get(name)
    if skill is None:
        return f"错误：未知技能 '{name}'，可选：{sorted(SKILL_REGISTRY)}"
    return f"# {skill.display_name}（{skill.name}）\n\n{skill.body}"


def build_testcase_registry() -> ToolRegistry:
    """构建用例设计 capability 的完整工具集：通用工具 + load_skill。"""
    registry = build_generic_registry()
    registry.register(Tool(
        name="load_skill",
        description="加载一个测试维度技能的完整规则（测试点生成规则 + 用例展开规则）。根据技能目录按需加载，可多次调用加载多个技能。",
        parameters={
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "技能名，如 boundary_value"},
            },
            "required": ["name"],
        },
        handler=_load_skill,
    ))
    return registry
