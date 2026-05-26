import { useEffect, useState } from 'react'
import NavBar, { BottomNav } from '../components/NavBar'
import './Industry.css'

interface IndustryItem {
  category: string; title: string; date_added?: string
  desc?: string; file: string
}

const CAT_NAMES = ['公司', '行业', '研报', '逻辑']
const CAT_ICONS: Record<string, string> = { '公司': '🏢', '行业': '📊', '研报': '📄', '逻辑': '🧠' }
const CAT_COLORS: Record<string, string> = {
  '公司': '#22c55e', '行业': '#3b82f6', '研报': '#a855f7', '逻辑': '#f59e0b',
}
const TAG_CLS: Record<string, string> = {
  '公司': 'company-tag', '行业': 'industry-tag', '研报': 'report-tag', '逻辑': 'logic-tag',
}

export default function Industry() {
  const [items, setItems] = useState<IndustryItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [activeCat, setActiveCat] = useState('')

  useEffect(() => { loadData() }, [])

  async function loadData() {
    setLoading(true); setError('')
    try {
      const r = await fetch('/api/industry/list')
      if (!r.ok) throw new Error('HTTP ' + r.status)
      const data = await r.json()
      const allItems = data.items || []
      setItems(allItems)
      // 找到第一个非空分类
      const grouped: Record<string, IndustryItem[]> = {}
      CAT_NAMES.forEach(c => grouped[c] = [])
      allItems.forEach((item: IndustryItem) => {
        const cat = item.category || '公司'
        if (!grouped[cat]) grouped[cat] = []
        grouped[cat].push(item)
      })
      const first = CAT_NAMES.find(c => (grouped[c] || []).length > 0) || '公司'
      setActiveCat(first)
    } catch (err: any) {
      setError(err.message)
    } finally { setLoading(false) }
  }

  function grouped(): Record<string, IndustryItem[]> {
    const g: Record<string, IndustryItem[]> = {}
    CAT_NAMES.forEach(c => g[c] = items.filter(i => (i.category || '公司') === c))
    return g
  }

  const g = grouped()

  return (
    <div className="page-container">
      <NavBar />

      <div className="header">
        <h1>🔬 行业追踪</h1>
        <div className="subtitle">公司分析 · 行业研究 · 机构研报</div>
      </div>

      <div className="container">
        {loading && (
          <div className="loading-area">
            <div className="spinner"></div>
            <br />加载中...
          </div>
        )}

        {error && (
          <div className="loading-area" style={{ color: '#e94560' }}>
            ❌ 加载失败: {error}
          </div>
        )}

        {!loading && !error && (
          <>
            {/* Category Tabs */}
            <div className="cat-tabs">
              {CAT_NAMES.map(cat => {
                const count = (g[cat] || []).length
                return (
                  <div
                    key={cat}
                    className={`cat-tab ${activeCat === cat ? 'active' : ''}`}
                    onClick={() => setActiveCat(cat)}
                    data-cat={cat}
                  >
                    {CAT_ICONS[cat]} {cat}
                    <span className="count">{count}</span>
                  </div>
                )
              })}
            </div>

            {/* Category Sections */}
            {CAT_NAMES.map(cat => {
              const sectionItems = g[cat] || []
              return (
                <div
                  key={cat}
                  className={`cat-section ${activeCat === cat ? 'active' : ''}`}
                  id={`cat-${cat}`}
                >
                  {sectionItems.length === 0 ? (
                    <div className="empty-cat">暂无{cat}分析</div>
                  ) : (
                    <div className="kb-grid">
                      {sectionItems.map((item, i) => (
                        <div key={item.file + i} className="kb-card">
                          <span className={`tag ${TAG_CLS[cat] || 'company-tag'}`}>
                            {CAT_ICONS[cat]} {cat}
                          </span>
                          <h3>{item.title}</h3>
                          {item.date_added && (
                            <div className="date">📅 收录 {item.date_added}</div>
                          )}
                          <p>{item.desc || '暂无摘要'}</p>
                          <div>
                            <a
                              className="btn btn-read"
                              href={`/tip-detail.html?type=industry&file=${encodeURIComponent(item.file)}`}
                            >
                              📖 阅读全文
                            </a>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </>
        )}
      </div>

      <div className="footer">3L 交易体系 · 行业追踪知识库</div>
      <BottomNav />
    </div>
  )
}
