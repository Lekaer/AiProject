"""PromptFoo Python 断言：评估测试用例 steps 可执行性。

由 phase2_case_expansion.yaml 中的 python 断言引用。
需要 OPENAI_API_KEY + OPENAI_BASE_URL 环境变量指向 DeepSeek。
"""

import json
import os
import re

from openai import OpenAI


def _parse_json(text: str) -> dict | None:
    """三级 fallback 解析，兼容 DeepSeek 返回的 markdown fence 等格式。"""
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

    # 只提取 steps 字段用于评分，减少输入长度
    try:
        cases = json.loads(output)
        steps_only = [
            {"id": c.get("id", f"TC-{i}"), "steps": c.get("steps", [])}
            for i, c in enumerate(cases)
        ]
        grading_input = json.dumps(steps_only, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, TypeError):
        grading_input = output

    rubric = (
        "Steps should be specific and directly executable by a tester.\n"
        "Rate on a scale of 1 to 5:\n"
        "- 1: Vague, abstract, no concrete actions\n"
        "- 2: Somewhat vague, missing key details\n"
        "- 3: Acceptable, can be followed with some interpretation\n"
        "- 4: Clear and specific, mostly actionable\n"
        "- 5: Highly specific, every step is directly executable without interpretation\n\n"
        "For each test case in the JSON array, evaluate its 'steps' field.\n"
        'Reply ONLY with: {"score": <number>, "reason": "<brief>"}'
    )

    client = OpenAI(api_key=api_key, base_url=base_url, timeout=120, max_retries=2)

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="deepseek-v4-pro",
                messages=[
                    {"role": "system", "content": "Reply with ONLY a JSON object. No markdown, no extra text."},
                    {"role": "user", "content": f"<Output>\n{grading_input}\n</Output>\n<Rubric>\n{rubric}\n</Rubric>"},
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
        if parsed:
            score = float(parsed.get("score", 0))
            reason = parsed.get("reason", "")
            return {
                "pass": score >= 3.5,
                "score": score / 5.0,
                "reason": f"Steps executability: {score}/5. {reason}",
            }

        # 尝试直接从文本中提取数字
        num_match = re.search(r"(\d+\.?\d*)", content)
        if num_match:
            score = float(num_match.group(1))
            if 1 <= score <= 5:
                return {
                    "pass": score >= 3.5,
                    "score": score / 5.0,
                    "reason": f"Steps executability: {score}/5 (extracted from: {content[:100]})",
                }

    return {"pass": False, "score": 0, "reason": f"Could not parse grader response: {content[:200]}"}
