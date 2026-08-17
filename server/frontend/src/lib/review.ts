/**
 * 兼容后端既有 opportunity 字段，但在页面上按“板块环境”表达。
 * 板块阶段不能替代个股买点，因此避免继续显示“机会”类结论。
 */
export function formatSectorEnvironment(value?: string, mainlineLevel?: string): string {
  const levelLabel = mainlineLevel === '主线'
    ? '10日强度前5候选'
    : mainlineLevel === '次级主线'
      ? '10日强度6–10候选'
      : mainlineLevel || '板块'
  const labels: Record<string, string> = {
    '主线回调': '10日强度前5候选 · 波谷',
    '次线机会': '10日强度6–10候选 · 波谷',
    '波谷观察': '10日强度榜外 · 波谷',
    '趋势延续': `${levelLabel} · 上升/波中`,
    '见顶风险': `${levelLabel} · 波峰风险`,
    '回调中': `${levelLabel} · 下跌/回调`,
    '主线观察': '10日强度前5候选 · 阶段待确认',
    '次级观察': '10日强度6–10候选 · 阶段待确认',
  }
  return labels[value || ''] || value || '--'
}
