/**
 * 兼容后端既有 opportunity 字段，但在页面上按“板块环境”表达。
 * 板块阶段不能替代个股买点，因此避免继续显示“机会”类结论。
 */
export function formatSectorEnvironment(value?: string, mainlineLevel?: string): string {
  const labels: Record<string, string> = {
    '主线回调': '主线 · 波谷',
    '次线机会': '次级主线 · 波谷',
    '波谷观察': '非主线 · 波谷',
    '趋势延续': `${mainlineLevel || '板块'} · 上升/波中`,
    '见顶风险': `${mainlineLevel || '板块'} · 波峰风险`,
    '回调中': `${mainlineLevel || '板块'} · 下跌/回调`,
    '主线观察': '主线 · 阶段待确认',
    '次级观察': '次级主线 · 阶段待确认',
  }
  return labels[value || ''] || value || '--'
}
