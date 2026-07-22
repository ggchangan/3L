import type { ReviewDataStatus as StatusContract, ReviewDataStatusItem } from '../lib/types'

interface Props {
  dataStatus?: StatusContract
}

const LABELS = {
  stocks: '个股',
  index: '指数',
  industry: '行业',
  concept: '概念',
} as const

function formatDate(value?: string) {
  const normalized = (value || '').replace(/-/g, '')
  if (normalized.length !== 8) return value || '无日期'
  return `${normalized.slice(4, 6)}-${normalized.slice(6, 8)}`
}

function coverageText(item: ReviewDataStatusItem) {
  if (item.status !== 'estimated' || item.coverage == null) return ''
  const detail = item.coverage_detail
  const counts = detail?.covered != null && detail?.expected != null
    ? `，${detail.covered}/${detail.expected}`
    : ''
  return ` ${(item.coverage * 100).toFixed(1)}%${counts}`
}

function statusText(item: ReviewDataStatusItem) {
  if (item.status === 'confirmed') return '正式数据'
  if (item.status === 'estimated') return `当日预估${coverageText(item)}`
  if (item.status === 'stale') return '待补齐'
  return '状态未知'
}

export default function ReviewDataStatus({ dataStatus }: Props) {
  if (!dataStatus) return null

  const keys = ['stocks', 'index', 'industry', 'concept'] as const
  const items = keys.map(key => ({
    key,
    label: LABELS[key],
    value: dataStatus[key] || { status: 'unknown' as const },
  }))
  const hasEstimate = items.some(item => item.value.status === 'estimated')
  const hasStale = items.some(item => item.value.status === 'stale' || item.value.status === 'unknown')

  return (
    <div className={`review-data-status${hasStale ? ' warning' : ''}`} role="status">
      <div className="review-data-status-title">当日复盘数据</div>
      <div className="review-data-status-items">
        {items.map(item => (
          <span className={`review-data-chip ${item.value.status}`} key={item.key}>
            {item.label} {formatDate(item.value.date || item.value.confirmed_date)} · {statusText(item.value)}
          </span>
        ))}
      </div>
      {hasEstimate && (
        <div className="review-data-status-note">
          当日预估可用于复盘；未覆盖项目已阻断交易指令。次日 06:00 将使用正式 THS 日线校准。
        </div>
      )}
      {!hasEstimate && hasStale && (
        <div className="review-data-status-note">
          部分数据尚未达到目标交易日，相关结论不可作为交易指令。
        </div>
      )}
    </div>
  )
}
