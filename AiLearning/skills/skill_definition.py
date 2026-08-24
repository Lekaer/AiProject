"""测试维度技能加载器：以 SKILL.md 文件为唯一数据源（M2-4）。

每个技能一个目录：AiLearning/skills/<name>/SKILL.md
- frontmatter：name / display_name / description（description 决定触发，含负边界）
- body：何时使用 / 测试点生成规则 / 用例展开规则 / 反例

本模块扫描 skills/*/SKILL.md 解析出 Skill 对象，对外保持历史接口不变：
Skill / SKILL_REGISTRY / SKILL_BATCHES / build_skills_catalog / get_skills_by_names
（旧 workflow 的 agents/testcase_design_agent.py 依赖这些符号和字段）。

规则内容只在 SKILL.md 里维护，本文件不含任何技能文案。
"""

import os
import re
from dataclasses import dataclass

SKILLS_DIR = os.path.dirname(os.path.abspath(__file__))


@dataclass(frozen=True)
class Skill:
    """测试维度技能，定义测试点生成规则和用例展开规则。"""

    name: str              # 唯一标识，如 "boundary_value"
    display_name: str      # 中文名，如 "边界值分析"
    description: str       # 触发说明（含负边界），决定模型何时加载
    test_point_rules: str  # Phase 1: 测试点生成规则（从 SKILL.md 对应小节解析）
    test_case_rules: str   # Phase 2: 用例展开规则（从 SKILL.md 对应小节解析）
    body: str              # SKILL.md 正文全文（何时使用/规则/反例），load_skill 直接返回


def _parse_skill_md(path: str) -> Skill:
    """解析单个 SKILL.md：frontmatter 取元数据，body 按 ## 小节拆分。"""
    with open(path, encoding="utf-8") as f:
        text = f.read()

    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        raise ValueError(f"{path} 缺少 frontmatter")
    frontmatter, body = m.group(1), m.group(2).strip()

    meta: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()

    sections: dict[str, str] = {}
    current: str | None = None
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = ""
        elif current is not None:
            sections[current] += line + "\n"

    return Skill(
        name=meta["name"],
        display_name=meta.get("display_name", meta["name"]),
        description=meta["description"],
        test_point_rules=sections.get("测试点生成规则", "").strip(),
        test_case_rules=sections.get("用例展开规则", "").strip(),
        body=body,
    )


def _load_registry() -> dict[str, Skill]:
    """扫描 skills/*/SKILL.md 构建注册表（按名称排序，保证目录稳定）。

    frontmatter 标 `registry: false` 的技能不进注册表——它们不供生成阶段选择
    （如 red_team 审查技能由审查 loop 直接读取，见 capabilities/adversarial_review.py）。
    """
    registry: dict[str, Skill] = {}
    for entry in sorted(os.listdir(SKILLS_DIR)):
        path = os.path.join(SKILLS_DIR, entry, "SKILL.md")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                head = f.read(2048)
            if re.search(r"^registry:\s*false\s*$", head, re.MULTILINE):
                continue
            skill = _parse_skill_md(path)
            registry[skill.name] = skill
    return registry


SKILL_REGISTRY: dict[str, Skill] = _load_registry()

# 模块级常量（历史接口，旧代码直接引用）
SKILL_BOUNDARY_VALUE = SKILL_REGISTRY["boundary_value"]
SKILL_EXCEPTION_PATH = SKILL_REGISTRY["exception_path"]
SKILL_PERMISSION_SECURITY = SKILL_REGISTRY["permission_security"]
SKILL_STATE_MACHINE = SKILL_REGISTRY["state_machine"]
SKILL_DATA_CONSISTENCY = SKILL_REGISTRY["data_consistency"]
SKILL_COMBINATORIAL = SKILL_REGISTRY["combinatorial"]

# ═══════════════════════════════════════════════════════════════════════
# 批次分组：相近 Skill 合并为一次 LLM 调用（旧 workflow 使用）
# ═══════════════════════════════════════════════════════════════════════

SKILL_BATCHES = [
    {
        "group_name": "边界与异常",
        "skills": ["boundary_value", "exception_path"],
    },
    {
        "group_name": "权限与状态",
        "skills": ["permission_security", "state_machine"],
    },
    {
        "group_name": "数据与组合",
        "skills": ["data_consistency", "combinatorial"],
    },
]


def build_skills_catalog() -> str:
    """生成供 LLM 选择的技能目录文本。"""
    lines = []
    for skill in SKILL_REGISTRY.values():
        lines.append(f"- {skill.name}（{skill.display_name}）：{skill.description}")
    return "\n".join(lines)


def get_skills_by_names(names: list[str]) -> list[Skill]:
    """按名称获取 Skill 列表，忽略不存在的名称。"""
    return [SKILL_REGISTRY[n] for n in names if n in SKILL_REGISTRY]
