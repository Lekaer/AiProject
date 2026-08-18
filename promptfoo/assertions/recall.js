// M3 债 1：缺陷库检索命中断言。
// 金标准：给定任务查询，目标缺陷必须出现在 top-3 命中里。

function assertHit(expectedId, label) {
  return function (output, context) {
    const meta = (context.providerResponse || {}).metadata || {};
    const hits = Array.isArray(meta.hit_ids) ? meta.hit_ids : [];
    if (hits.includes(expectedId)) {
      return { pass: true, score: 1, reason: `${label}：命中 ${expectedId}（top3=${JSON.stringify(hits)}）` };
    }
    return { pass: false, score: 0, reason: `${label}：未命中 ${expectedId}，实际 top3=${JSON.stringify(hits)}` };
  };
}

module.exports = {
  assertDef003: assertHit('DEF-003', '增店数量上限'),
  assertDef007: assertHit('DEF-007', '增店重复提交'),
  assertDef001: assertHit('DEF-001', '签约合同生成失败'),
  assertDef004: assertHit('DEF-004', '退出状态未流转'),
  assertDef005: assertHit('DEF-005', '越权查看资金'),
  assertDef006: assertHit('DEF-006', '清算精度误差'),
  assertDef008: assertHit('DEF-008', '续签增店互斥'),
};
