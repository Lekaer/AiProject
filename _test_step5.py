"""Step 5 端到端测试"""
import json
import re
import logging
logging.basicConfig(level=logging.WARNING)

from AiLearning.router.agent_router import dispatch

# 需要找到正确的 collection_name
from AiLearning.rag.vector_store import list_collections_by_prefix
cols = list_collections_by_prefix("test__")
print("Collections:", [c["name"] for c in cols])
collection_name = cols[0]["name"] if cols else None
print("Using collection:", collection_name)

with open("/Users/kaka/PycharmProjects/AiProject/_test_requirement.txt") as f:
    req = f.read()

response = dispatch(
    question="为批量入驻功能设计测试用例",
    app="testcase_design",
    collection_name=collection_name,
    requirement_doc=req,
    reference_case_filenames=["_test_reference_cases.txt"],
)

print("\nAgent:", response.agent_name)
print("Metadata:", json.dumps(response.metadata, ensure_ascii=False, indent=2))
print("Answer length:", len(response.answer))

# 保存原始答案
with open("/tmp/testcase_design_answer.txt", "w") as f:
    f.write(response.answer)

# 解析 JSON
answer = response.answer.strip()
json_str = None

# 1) markdown code fence
m = re.search(r"```(?:json)?\s*([\s\S]*?)```", answer)
if m:
    json_str = m.group(1)
# 2) raw JSON array
elif answer.startswith("["):
    json_str = answer
# 3) find first JSON array
else:
    m = re.search(r"\[[\s\S]*\]", answer)
    if m:
        json_str = m.group(0)

if json_str:
    cases = json.loads(json_str)
    print(f"\n用例数: {len(cases)}")

    from collections import Counter
    types = Counter(c["type"] for c in cases)
    print("类型分布:")
    for t, n in types.items():
        print(f"  {t}: {n}")

    print("\n前5条用例:")
    for c in cases[:5]:
        print(f"  {c['id']} | {c['title']} | {c['type']}")
        print(f"    前置: {c['precondition'][:80]}...")
        print(f"    步骤: {len(c['steps'])} steps")
        print()

    # 验证每条用例字段完整
    required_fields = ["id", "title", "type", "precondition", "steps", "expected"]
    for c in cases:
        for f in required_fields:
            assert f in c, f"Missing field {f} in {c.get('id', '?')}"
    print("所有用例字段完整 ✅")
else:
    print("无法解析 JSON")
    print("Answer length:", len(answer))
    print("Last 500 chars:", repr(answer[-500:]))
    print("Around error (1320-1450):", repr(answer[1300:1450]))
