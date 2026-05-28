interface Props {
  dates: string[]
  currentDate: string
}

export default function HistoryReview({ dates, currentDate }: Props) {
  const filtered = dates.filter(d => d !== currentDate).sort().reverse()

  if (!filtered.length) return <div className="empty">暂无历史复盘数据</div>

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {filtered.map(date => (
        <div key={date} style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '6px 10px', background: 'rgba(255,255,255,0.02)', borderRadius: 8,
        }}>
          <span style={{ color: '#e94560', fontSize: 13, fontWeight: 'bold' }}>{date}</span>
          <a href={`/review?date=${date}`} style={{ color: '#4ecdc4', textDecoration: 'none', fontSize: 12 }}>
            查看复盘 →
          </a>
        </div>
      ))}
    </div>
  )
}
