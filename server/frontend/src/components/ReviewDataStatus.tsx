import type { ReviewData } from '../lib/types'

type Props = Pick<ReviewData, 'data_dates' | 'data_freshness'>

const LABELS = {
  stocks: '个股',
  index: '指数',
  sectors: '板块',
} as const

function formatDate(value?: string) {
  const normalized = (value || '').replace(/-/g, '')
  if (normalized.length !== 8) return value || '无日期'
  return `${normalized.slice(4, 6)}-${normalized.slice(6, 8)}`
}

export default function ReviewDataStatus({ data_dates, data_freshness }: Props) {
  if (!data_dates && !data_freshness) return null

  const items = (['stocks', 'index', 'sectors'] as const).map(key => {
    const freshness = data_freshness?.[key] || 'unknown'
    return {
      key,
      label: LABELS[key],
      date: formatDate(data_dates?.[key]),
      freshness,
      statusText: freshness === 'current'
        ? '已确认'
        : freshness === 'stale'
          ? '待补齐'
          : '状态未知',
    }
  })
  const sectorsPending = data_freshness?.sectors === 'stale'

  return (
    <div className={`review-data-status${sectorsPending ? ' warning' : ''}`} role="status">
      <div className="review-data-status-title">当日复盘数据</div>
      <div className="review-data-status-items">
        {items.map(item => (
          <span className={`review-data-chip ${item.freshness}`} key={item.key}>
            {item.label} {item.date} · {item.statusText}
          </span>
        ))}
      </div>
      {sectorsPending && (
        <div className="review-data-status-note">
          主线排名暂沿用上一交易日板块日线，将于次日 06:00 自动校准。
        </div>
      )}
    </div>
  )
}