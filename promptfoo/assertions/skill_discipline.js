// M2-5 skill 纪律断言：加载集合 ⊆ 证据支持集（判纪律，不判数字）。
// 原则（learning-records/0017）：多加载=稀释质量是实测失败模式，必须红；
// 少加载有评审/场景层兜，所以允许真子集，但要求非空且 ≤2。

function getMeta(context) {
  const resp = context.providerResponse || {};
  const meta = resp.metadata || {};
  return {
    calledTools: Array.isArray(meta.called_tools) ? meta.called_tools : [],
    steps: typeof meta.steps === 'number' ? meta.steps : -1,
    stopReason: meta.stop_reason || '',
  };
}

function check(context, evidenceSet, label) {
  const meta = getMeta(context);
  const loaded = [...new Set(
    meta.calledTools.filter((t) => t.name === 'load_skill').map((t) => (t.args || {}).name)
  )];
  const outside = loaded.filter((s) => !evidenceSet.includes(s));
  if (outside.length > 0) {
    return {
      pass: false, score: 0,
      reason: `${label}：加载了证据外的 skill ${JSON.stringify(outside)}（证据集 ${JSON.stringify(evidenceSet)}，实际加载 ${JSON.stringify(loaded)}）`,
    };
  }
  if (loaded.length === 0) {
    return { pass: false, score: 0, reason: `${label}：未加载任何 skill（凭经验生成是被禁止的）` };
  }
  if (loaded.length > 2) {
    return { pass: false, score: 0, reason: `${label}：加载 ${loaded.length} 个 skill，超过上限 2（过度加载）` };
  }
  if (!meta.calledTools.some((t) => t.name === 'write_output')) {
    return { pass: false, score: 0, reason: `${label}：未调用 write_output 落盘` };
  }
  if (meta.stopReason !== 'final') {
    return { pass: false, score: 0, reason: `${label}：stop_reason 应为 final，实际为 ${meta.stopReason}` };
  }
  return { pass: true, score: 1, reason: `${label}：加载 ${JSON.stringify(loaded)} ⊆ 证据集，${meta.steps} 步结束` };
}

// 同步类任务（第三方数据同步）→ 证据集 {data_consistency, exception_path}
function assertSyncTask(output, context) {
  return check(context, ['data_consistency', 'exception_path'], '同步任务');
}

// 限额录入任务（显式数值约束）→ 证据集 {boundary_value}
function assertBoundaryTask(output, context) {
  return check(context, ['boundary_value'], '限额录入任务');
}

// 审批驳回重提任务（状态流转）→ 证据集 {state_machine}
function assertStateTask(output, context) {
  return check(context, ['state_machine'], '状态流转任务');
}

// 优化类任务（change=modified）→ 证据集 {regression}
function assertRegressionTask(output, context) {
  return check(context, ['regression'], '优化类任务');
}

module.exports = { assertSyncTask, assertBoundaryTask, assertStateTask, assertRegressionTask };
