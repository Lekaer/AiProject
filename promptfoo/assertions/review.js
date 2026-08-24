// M3 债 1：对抗审查断言——固定输入下必须产出缺口报告。

function getMeta(context) {
  const resp = context.providerResponse || {};
  const meta = resp.metadata || {};
  return {
    calledTools: Array.isArray(meta.called_tools) ? meta.called_tools : [],
    stopReason: meta.stop_reason || '',
    gapCount: typeof meta.gap_count === 'number' ? meta.gap_count : -1,
  };
}

// 已知有缺口的用例集：必须发现至少 minGaps 个缺口，且落盘、final
function assertFindsGaps(output, context) {
  const meta = getMeta(context);
  const vars = context.vars || {};
  const minGaps = vars.min_gaps || 1;

  if (!meta.calledTools.some((t) => t.name === 'write_output')) {
    return { pass: false, score: 0, reason: '审查未调用 write_output 落盘' };
  }
  if (meta.stopReason !== 'final') {
    return { pass: false, score: 0, reason: `stop_reason 应为 final，实际 ${meta.stopReason}` };
  }
  if (meta.gapCount < minGaps) {
    return { pass: false, score: 0, reason: `缺口数应 ≥ ${minGaps}，实际 ${meta.gapCount}` };
  }
  return { pass: true, score: 1, reason: `发现 ${meta.gapCount} 个缺口并落盘` };
}

module.exports = { assertFindsGaps };
