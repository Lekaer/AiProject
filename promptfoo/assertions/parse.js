// M2-5 parse 结构断言：结构合法性 + 关键元素存在性。
// 原则：parse 输出跨轮不稳定，断言区间/存在性，不断言精确数量。

function getMeta(context) {
  const resp = context.providerResponse || {};
  return resp.metadata || {};
}

// 通用检查：valid + flows/tasks/rules 下限 + open_questions 下限 + flow id 格式
function check(context, minTasks, minRules, minOpenQuestions, label) {
  const meta = getMeta(context);
  if (!meta.valid) {
    return { pass: false, score: 0, reason: `解析未通过校验：${meta.error || '未知错误'}` };
  }
  const s = meta.stats || {};
  if ((s.flows || 0) < 1) {
    return { pass: false, score: 0, reason: `${label}：flows 应 ≥ 1，实际 ${s.flows}` };
  }
  if ((s.tasks || 0) < minTasks) {
    return { pass: false, score: 0, reason: `${label}：tasks 应 ≥ ${minTasks}，实际 ${s.tasks}` };
  }
  if ((s.rules || 0) < minRules) {
    return { pass: false, score: 0, reason: `${label}：rules 应 ≥ ${minRules}，实际 ${s.rules}` };
  }
  if ((meta.open_questions || []).length < minOpenQuestions) {
    return { pass: false, score: 0, reason: `${label}：open_questions 应 ≥ ${minOpenQuestions}，实际 ${(meta.open_questions || []).length}` };
  }
  const badId = (meta.flow_ids || []).find((id) => !/^F[0-9]+$/.test(id));
  if (badId) {
    return { pass: false, score: 0, reason: `${label}：flow id 格式非法：${badId}` };
  }
  return {
    pass: true, score: 1,
    reason: `${label}：结构合法（${s.flows}流程/${s.tasks}任务/${s.rules}规则，open_questions=${(meta.open_questions || []).length}，assumed=${s.assumed}）`,
  };
}

// 真实 PRD（已知不完善）：结构下限 + 必须发现待确认问题（存在性，不断言条数）
function assertRealDoc(output, context) {
  return check(context, 3, 5, 1, '真实PRD');
}

// 极简文本需求：能解析出最小结构即可
function assertInlineText(output, context) {
  return check(context, 1, 1, 0, '极简文本');
}

module.exports = { assertRealDoc, assertInlineText };
