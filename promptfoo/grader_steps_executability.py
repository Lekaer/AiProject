"""PromptFoo Python 断言：评估测试用例 steps 可执行性（二元检查表）。

由 phase2_case_expansion.yaml 中的 python 断言引用。
需要 OPENAI_API_KEY + OPENAI_BASE_URL 环境变量指向 DeepSeek。

改进：从 1-5 数值量表改为 5 项二元条件检查，每项 pass/fail。
  最终 score = 通过的用例数 / 总用例数，阈值 ≥ 0.7 即 70% 以上用例全部条件通过。
"""

import json
import os
import re

from openai import OpenAI


_CHECKLIST_RUBRIC = (
    "For each test case's 'steps' field, evaluate these 5 conditions (true/false):\n"
    "1. concrete_action: Every step contains a specific verb/action (e.g. 点击/输入/调用/查询/发送/修改/删除)\n"
    "2. clear_target: Every step specifies what to operate on (e.g. page element, API endpoint, input field)\n"
    "3. logical_order: Steps are sequenced so each step's output feeds the next (no orphaned actions)\n"
    "4. no_vagueness: No step requires the tester to guess (e.g. avoid 进行相应操作/执行验证/做检查)\n"
    "5. right_granularity: Steps are at the right level — not too coarse (登录系统 as one step) nor too fine (按键级别)\n"
    "\n"
    "A test case passes ONLY if ALL 5 conditions are true.\n"
    "\n"
    "Reply ONLY with a JSON object. No markdown, no extra text:\n"
    '{"checks": [{"id": "TC-001", "pass": true/false, "failed": ["condition_name", ...]}], '
    '"total_pass": N, "total": M}'
)


def _parse_json(text: str) -> dict | None:
    """三级 fallback 解析，兼容 markdown fence / 裸 JSON / 正则兜底。"""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def get_assert(output: str, context: dict) -> dict:
    """PromptFoo python 断言入口。"""
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com/v1")

    if not api_key:
        return {"pass": False, "score": 0, "reason": "OPENAI_API_KEY not set"}

    # 只提取 [id + steps] 用于评分，减少输入长度
    try:
        cases = json.loads(output)
        steps_only = [
            {"id": c.get("id", f"TC-{i + 1}"), "steps": c.get("steps", [])}
            for i, c in enumerate(cases)
        ]
        grading_input = json.dumps(steps_only, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        grading_input = output

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=120, max_retries=2)

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=[
                    {"role": "system", "content": "Reply with ONLY a JSON object. No markdown, no extra text."},
                    {"role": "user", "content": f"<Output>\n{grading_input}\n</Output>\n<Rubric>\n{_CHECKLIST_RUBRIC}\n</Rubric>"},
                ],
                temperature=0,
                max_tokens=4096,
            )
            content = (response.choices[0].message.content or "").strip()
        except Exception as e:
            if attempt < 2:
                continue
            return {"pass": False, "score": 0, "reason": f"API call failed after 3 retries: {e}"}

        if not content:
            if attempt < 2:
                continue
            return {"pass": False, "score": 0, "reason": "API returned empty response after 3 attempts"}

        parsed = _parse_json(content)
        if parsed and "checks" in parsed:
            checks = parsed["checks"]
            total = len(checks)
            passed = sum(1 for c in checks if c.get("pass"))
            pass_rate = passed / total if total > 0 else 0

            # 收集失败详情
            failures = [
                f"{c['id']}: {c.get('failed', [])}"
                for c in checks if not c.get("pass")
            ]
            reason = f"Steps executability: {passed}/{total} pass ({pass_rate:.0%})"
            if failures:
                reason += f". Failed: {'; '.join(failures[:3])}"
                if len(failures) > 3:
                    reason += f" ... +{len(failures) - 3} more"

            return {
                "pass": pass_rate >= 0.7,
                "score": pass_rate,
                "reason": reason,
            }

        # fallback: 尝试从文本中提取 pass count
        num_match = re.search(r"(\d+)\s*/\s*(\d+)", content)
        if num_match:
            passed = int(num_match.group(1))
            total = int(num_match.group(2))
            pass_rate = passed / total if total > 0 else 0
            return {
                "pass": pass_rate >= 0.7,
                "score": pass_rate,
                "reason": f"Steps executability: {passed}/{total} pass (extracted from text)",
            }

    return {"pass": False, "score": 0, "reason": f"Could not parse grader response: {content[:200]}"}
