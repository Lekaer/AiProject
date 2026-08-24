// M1 轨迹断言：从 provider metadata（called_tools/steps/stop_reason）判定 agent 行为。
// 用法：file://assertions/trajectory.js:assertBoundary 等。
// called_tools 结构：[{name: "load_skill", args: {name: "boundary_value"}}, ...]

function getMeta(context) {
  const resp = context.providerResponse || {};
  const meta = resp.metadata || {};
  return {
    calledTools: Array.isArray(meta.called_tools) ? meta.called_tools : [],
    steps: typeof meta.steps === 'number' ? meta.steps : -1,
    stopReason: meta.stop_reason || '',
  };
}

function loadedSkills(calledTools) {
  return calledTools.filter((t) => t.name === 'load_skill').map((t) => (t.args || {}).name);
}

function hasTool(calledTools, name) {
  return calledTools.some((t) => t.name === name);
}

function check(meta, expectedSkills, maxSteps) {
  // 加载集合精确匹配（与顺序无关、去重）：模型过度加载（多加载 skill）同样判失败
  const skills = [...new Set(loadedSkills(meta.calledTools))];
  const actual = new Set(skills);
  const expected = new Set(expectedSkills);
  const missing = expectedSkills.filter((s) => !actual.has(s));
  const extra = skills.filter((s) => !expected.has(s));
  if (missing.length > 0 || extra.length > 0) {
    return {
      pass: false, score: 0,
      reason: `load_skill 集合不精确匹配：期望 ${JSON.stringify(expectedSkills)}，实际 ${JSON.stringify(skills)}` +
        (missing.length ? `，缺少 ${JSON.stringify(missing)}` : '') +
        (extra.length ? `，多加载 ${JSON.stringify(extra)}` : ''),
    };
  }
  if (!hasTool(meta.calledTools, 'write_output')) {
    return { pass: false, score: 0, reason: '未调用 write_output 落盘' };
  }
  if (meta.stopReason !== 'final') {
    return { pass: false, score: 0, reason: `stop_reason 应为 final，实际为 ${meta.stopReason}` };
  }
  if (maxSteps && (meta.steps < 0 || meta.steps > maxSteps)) {
    return { pass: false, score: 0, reason: `steps 应 ≤ ${maxSteps}，实际为 ${meta.steps}` };
  }
  return { pass: true, score: 1, reason: `轨迹符合预期：加载技能精确匹配 ${JSON.stringify(skills)}，${meta.steps} 步结束` };
}

// 用例 1：边界值需求 → 加载集合必须精确等于 {boundary_value}
function assertBoundary(output, context) {
  return check(getMeta(context), ['boundary_value'], 10);
}

// 用例 2：异常路径需求 → 加载集合必须 ⊆ {exception_path, data_consistency} 且非空且 ≤2
// 归因记录（2026-08-06，M2-5 回归）：SKILL.md description 丰富化后，需求文本中的
// "更新订单状态（DB 写）+ 发送 MQ 消息"构成 data_consistency 的客观证据——
// "重点覆盖异常"是优先级声明不是排除声明，原期望"恰好 {exception_path}"是期望缝隙
// 而非模型错误（对照 learning-records/0005 假分歧）。故改为纪律断言：
// 判"加载 ⊆ 证据集"而非判精确数字；≤2 上限仍然拦截"全选 skill"失败模式。
function assertException(output, context) {
  const meta = getMeta(context);
  const skills = [...new Set(loadedSkills(meta.calledTools))];
  const evidence = ['exception_path', 'data_consistency'];
  const outside = skills.filter((s) => !evidence.includes(s));
  if (outside.length > 0) {
    return { pass: false, score: 0, reason: `加载了证据外 skill ${JSON.stringify(outside)}，实际 ${JSON.stringify(skills)}` };
  }
  if (skills.length === 0) {
    return { pass: false, score: 0, reason: '未加载任何 skill' };
  }
  if (skills.length > 2) {
    return { pass: false, score: 0, reason: `加载 ${skills.length} 个 skill 超过上限 2（过度加载）` };
  }
  if (!hasTool(meta.calledTools, 'write_output')) {
    return { pass: false, score: 0, reason: '未调用 write_output 落盘' };
  }
  if (meta.stopReason !== 'final') {
    return { pass: false, score: 0, reason: `stop_reason 应为 final，实际为 ${meta.stopReason}` };
  }
  return { pass: true, score: 1, reason: `加载 ${JSON.stringify(skills)} ⊆ 证据集，${meta.steps} 步结束` };
}

// 用例 3：多维度需求 → 加载集合必须精确等于 {boundary_value, exception_path}
function assertMulti(output, context) {
  return check(getMeta(context), ['boundary_value', 'exception_path'], 10);
}

module.exports = { assertBoundary, assertException, assertMulti };
