import { useEffect, useState } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import './Tips.css'

interface TipItem {
  title: string; file: string; date_added?: string
  desc?: string; is_journal?: boolean
}

interface TipsData {
  tips: TipItem[]
}

export default function Tips() {
  const [tips, setTips] = useState<TipItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true); setError('')
    try {
      const r = await fetch('/api/tips')
      if (!r.ok) throw new Error('HTTP ' + r.status)
      const data: TipsData = await r.json()
      setTips(data.tips || [])
    } catch (err: any) {
      setError(err.message)
    } finally { setLoading(false) }
  }

  return (
    <div className="page-container">
      <NavBar />

      <div className="header">
        <h1>📝 交易技巧</h1>
        <div className="subtitle">简放公众号文章 · 持续收录中</div>
      </div>

      <div className="container">
        {loading && (
          <div id="tips-list" className="loading">
            <div className="spinner"></div><br />加载中...
          </div>
        )}

        {error && (
          <div id="tips-list" className="empty">❌ 加载失败: {error}</div>
        )}

        {!loading && !error && tips.length === 0 && (
          <div id="tips-list" className="empty">暂无交易技巧</div>
        )}

        {!loading && !error && tips.length > 0 && (
          <div id="tips-list" className="tips-grid">
            {tips.map((t, i) => {
              const readLink = `/tip-detail.html?type=tips&file=${encodeURIComponent(t.file)}`
              return (
                <div className="tip-card" key={t.file + i}>
                  {t.is_journal && (
                    <div>
                      <span className="badge">📖 技巧</span>
                      <span className="badge badge-tool">✍️ 互动工具</span>
                    </div>
                  )}
                  <h3>{t.title}</h3>
                  {t.date_added && <div className="date">📅 收录 {t.date_added}</div>}
                  <p>{t.desc || '暂无摘要'}</p>
                  <div className="tip-actions">
                    <a className="btn btn-read" href={readLink}>📖 阅读文章</a>
                    {t.is_journal && (
                      <a className="btn btn-tool" href="/journal.html">✍️ 写日志</a>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>

      <div className="footer">3L 交易体系 · 交易技巧知识库</div>
      <BottomNav />
    </div>
  )
}
