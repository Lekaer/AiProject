"""临时验证脚本：pipeline 的 all_rule_ids 路径修复确认（P2 练习回收用）。"""

from AiLearning.capabilities.requirement_model import RequirementModel

m = RequirementModel.model_validate({
    "title": "t", "summary": "s",
    "flows": [{
        "id": "F1", "name": "f", "preconditions": [], "relations": [],
        "tasks": [{
            "id": "F1.T1", "name": "t", "type": "录入", "description": "d",
            "relations": [], "produces": [],
            "rules": [{"id": "F1.T1.R1", "condition": "c", "expected": "e"}],
        }],
    }],
    "open_questions": [],
})

print("all_rules:", {r.id for r in m.all_rules})

# 顺便验证 pipeline 里那行的写法（model.all_rules）
all_rule_ids = {r.id for r in m.all_rules}
print("all_rule_ids:", all_rule_ids)
