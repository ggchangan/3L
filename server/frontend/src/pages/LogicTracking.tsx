import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import NavBar from '../components/NavBar'

interface LogicTag {
  id: string
  name: string
  description?: string
  related_industries?: string[]
  related_stocks?: string[]
  tier: 'focused' | 'core' | 'watch'
  tier_override?: boolean
  event_count?: number
  verify_rate?: number
  earnings_verify_rate?: number
  created_at?: string
  updated_at?: string
}

interface TagForm {
  id: string
  name: string
  description: string
  related_industries: string
  related_stocks: string
  tier: 'focused' | 'core' | 'watch'
}

const EMPTY_FORM: TagForm = {
  id: '',
  name: '',
  description: '',
  related_industries: '',
  related_stocks: '',
  tier: 'watch',
}

const COLORS: Record<string, string> = {
  focused: '#e94560',
  core: '#4ecdc4',
  watch: '#888',
}

const LABELS: Record<string, string> = {
  focused: '🌟 聚焦',
  core: '📌 核心',
  watch: '👁️ 观察',
}

export default function LogicTracking() {
  const [tags, setTags] = useState<LogicTag[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<LogicTag | null>(null)
  const [form, setForm] = useState<TagForm>(EMPTY_FORM)
  const [error, setError] = useState('')
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({
    core: true,
    watch: true,
  })
  const [search, setSearch] = useState('')
  const navigate = useNavigate()
  const [feedUrl, setFeedUrl] = useState('')
  const [feedLoading, setFeedLoading] = useState(false)
  const [feedResult, setFeedResult] = useState<any>(null)
  const [feedSelected, setFeedSelected] = useState<string[]>([])
  const [feedError, setFeedError] = useState('')
  const [feedTab, setFeedTab] = useState('wechat') // wechat | report | douyin
  const [wechatSubtype, setWechatSubtype] = useState('industry') // industry | review | other
  const [pdfFile, setPdfFile] = useState<File | null>(null)

  // Forecast state
  const [showForecast, setShowForecast] = useState(false)
  const [forecasts, setForecasts] = useState<any[]>([])
  const [fcForm, setFcForm] = useState({ title: '', event_date: '', prediction: '', logic_tags: '' })
  const [fcTab, setFcTab] = useState('list') // list | add

  // Entries state
  const [entries, setEntries] = useState<any[]>([])
  const [entriesLoading, setEntriesLoading] = useState(false)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [showGraph, setShowGraph] = useState(false)

  useEffect(() => { fetchTags(); fetchEntries() }, [])

  const fetchEntries = async () => {
    setEntriesLoading(true)
    try {
      const r = await fetch('/api/logic-tracking/entries')
      const d = await r.json()
      setEntries(d.entries || [])
    } catch (e) {
      console.error('加载条目失败:', e)
    } finally {
      setEntriesLoading(false)
    }
  }

  const fetchTags = async () => {
    try {
      const r = await fetch('/api/logic-tracking/tags')
      const d = await r.json()
      setTags(d.tags || [])
    } catch (e) {
      console.error('加载逻辑标签失败:', e)
    } finally {
      setLoading(false)
    }
  }

  const openNew = () => {
    setEditing(null)
    setForm(EMPTY_FORM)
    setError('')
    setShowForm(true)
  }

  const openEdit = (tag: LogicTag) => {
    setEditing(tag)
    setForm({
      id: tag.id,
      name: tag.name,
      description: tag.description || '',
      related_industries: (tag.related_industries || []).join(','),
      related_stocks: (tag.related_stocks || []).join(','),
      tier: tag.tier,
    })
    setError('')
    setShowForm(true)
  }

  const handleSave = async () => {
    if (!form.id.trim() || !form.name.trim()) {
      setError('ID和名称不能为空')
      return
    }
    const payload: LogicTag = {
      id: form.id.trim(),
      name: form.name.trim(),
      description: form.description.trim(),
      related_industries: form.related_industries.split(',').map(s => s.trim()).filter(Boolean),
      related_stocks: form.related_stocks.split(',').map(s => s.trim()).filter(Boolean),
      tier: form.tier,
      tier_override: false,
      event_count: editing?.event_count || 0,
      verify_rate: editing?.verify_rate || 0,
      earnings_verify_rate: editing?.earnings_verify_rate || 0,
    }

    try {
      const url = editing
        ? '/api/logic-tracking/tags/update'
        : '/api/logic-tracking/tags/add'
      const r = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const result = await r.json()
      if (result.success) {
        setShowForm(false)
        fetchTags()
      } else {
        setError(result.error || '保存失败')
      }
    } catch (e: any) {
      setError('网络错误: ' + e.message)
    }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('确定删除这个逻辑标签？')) return
    try {
      const r = await fetch('/api/logic-tracking/tags/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      })
      const result = await r.json()
      if (result.success) fetchTags()
    } catch (e) {
      console.error('删除失败:', e)
    }
  }

  const handleDeleteEntry = async (entryId: string) => {
    if (!confirm('确定删除这条投喂记录？')) return
    try {
      const r = await fetch('/api/logic-tracking/entries/delete', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: entryId }),
      })
      const data = await r.json()
      if (data.success) fetchEntries()
    } catch (e) {
      console.error('删除失败:', e)
    }
  }

  const openForecast = async () => {
    setFcTab('list')
    setFcForm({ title: '', event_date: '', prediction: '', logic_tags: '' })
    setShowForecast(true)
    try {
      const r = await fetch('/api/logic-tracking/forecasts?upcoming=30')
      const d = await r.json()
      setForecasts(d.forecasts || [])
    } catch { setForecasts([]) }
  }

  const handleAddForecast = async () => {
    if (!fcForm.title.trim() || !fcForm.event_date) return
    try {
      const r = await fetch('/api/logic-tracking/forecasts/add', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          id: 'fcst-' + Date.now().toString(36),
          type: 'forecast',
          subtype: 'manual',
          title: fcForm.title.trim(),
          event_date: fcForm.event_date,
          prediction: fcForm.prediction.trim(),
          logic_tags: fcForm.logic_tags.split(',').map(s => s.trim()).filter(Boolean),
          related_stocks: [],
          remind_before_days: 3,
          created_at: new Date().toISOString().slice(0, 10),
        }),
      })
      const data = await r.json()
      if (data.success) {
        setFcForm({ title: '', event_date: '', prediction: '', logic_tags: '' })
        setFcTab('list')
        // Refresh
        const r2 = await fetch('/api/logic-tracking/forecasts?upcoming=30')
        const d2 = await r2.json()
        setForecasts(d2.forecasts || [])
      }
    } catch {}
  }

  const handleDeleteForecast = async (id: string) => {
    if (!confirm('确定删除？')) return
    try {
      await fetch('/api/logic-tracking/forecasts/delete', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      })
      setForecasts(prev => prev.filter(f => f.id !== id))
    } catch {}
  }

const handleFeedProcess = async () => {
    if (!feedUrl.trim()) { setFeedError('请输入链接'); return }
    setFeedLoading(true)
    setFeedError('')
    setFeedResult(null)
    try {
      const r = await fetch('/api/logic-tracking/feed/process', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: feedUrl.trim(),
          source_type: feedTab,
          source_subtype: feedTab === 'wechat' ? wechatSubtype : '',
        }),
      })
      const data = await r.json()
      if (data.error) { setFeedError(data.error); return }
      setFeedResult(data)
      if (data.recommended_tags) {
        setFeedSelected(data.recommended_tags.map((t: any) => t.tag_id))
      }
    } catch (e: any) {
      setFeedError('处理失败: ' + e.message)
    } finally {
      setFeedLoading(false)
    }
  }

  const handleFeedSave = async () => {
    if (!feedResult) return
    // Extract industries and companies from suggested_new_tags
    const allIndustries: string[] = []
    const allCompanies: {code:string,name:string}[] = []
    const allLogics: string[] = []
    if (feedResult.suggested_new_tags) {
      for (const st of feedResult.suggested_new_tags) {
        if (st.name) allLogics.push(st.name)
        if (st.industries) {
          for (const ind of st.industries) {
            if (!allIndustries.includes(ind)) allIndustries.push(ind)
          }
        }
        if (st.related_stocks) {
          for (const s of st.related_stocks) {
            const code = typeof s === 'string' ? s : s.code
            const name = typeof s === 'string' ? '' : s.name || ''
            if (!allCompanies.find(c => c.code === code)) {
              allCompanies.push({code, name})
            }
          }
        }
      }
    }
    try {
      const r = await fetch('/api/logic-tracking/feed/save', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: feedResult.title,
          summary: feedResult.summary,
          core_logic: feedResult.core_logic || '',
          source_name: feedResult.source_name,
          source_type: feedTab,
          source_subtype: feedTab === 'wechat' ? wechatSubtype : '',
          url: feedResult.url,
          logic_tags: feedSelected,
          industries: allIndustries,
          companies: allCompanies,
          extracted_logics: allLogics,
        }),
      })
      const data = await r.json()
      if (data.success) {
        setFeedResult(null)
        setFeedUrl('')
        setFeedError('')
        fetchTags()
        fetchEntries()
      } else {
        setFeedError(data.error || '保存失败')
      }
    } catch (e: any) {
      setFeedError('保存失败: ' + e.message)
    }
  }

  const renderTagCard = (tag: LogicTag) => (
    <div key={tag.id} className="info-card" style={{ marginBottom: 8, padding: 10, position: 'relative', cursor: 'pointer' }}
      onClick={() => navigate(`/logic-tracking/${tag.id}`)}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontWeight: 'bold', color: COLORS[tag.tier] || '#eee' }}>
          {tag.name}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="action-btn" onClick={(e) => { e.stopPropagation(); openEdit(tag); }} style={{ fontSize: 11, padding: '2px 6px' }}>
            编辑
          </button>
          <button className="action-btn" onClick={(e) => { e.stopPropagation(); handleDelete(tag.id); }} style={{ fontSize: 11, padding: '2px 6px', color: '#e94560' }}>
            删除
          </button>
        </div>
      </div>
      {tag.description && (
        <div style={{ color: '#aaa', fontSize: 12, marginTop: 4 }}>{tag.description}</div>
      )}
      <div style={{ display: 'flex', gap: 12, marginTop: 6, fontSize: 11, color: '#888' }}>
        {tag.related_stocks && tag.related_stocks.length > 0 && (
          <span>📈 {tag.related_stocks.length}只关联个股</span>
        )}
        <span>📄 {tag.event_count || 0}个事件</span>
        {tag.verify_rate !== undefined && tag.verify_rate > 0 && (
          <span style={{ color: tag.verify_rate >= 0.6 ? '#4ecdc4' : '#e94560' }}>
            📊 {Math.round(tag.verify_rate * 100)}%印证
          </span>
        )}
      </div>
    </div>
  )

  const renderSection = (tier: string, title: string) => {
    const sectionTags = tags.filter(t => t.tier === tier)
      .filter(t => !search || t.name.toLowerCase().includes(search.toLowerCase()) || t.id.toLowerCase().includes(search.toLowerCase()))
    if (sectionTags.length === 0) return null
    const isCollapsed = collapsed[tier]
    const maxShow = tier === 'focused' ? undefined : (isCollapsed ? 2 : undefined)
    const displayTags = maxShow ? sectionTags.slice(0, maxShow) : sectionTags
    const hasMore = maxShow ? sectionTags.length > maxShow : false

    return (
      <div className="section" style={{ marginTop: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <h3 style={{ margin: 0, color: COLORS[tier] }}>{title}（{sectionTags.length}）</h3>
          {tier !== 'focused' && sectionTags.length > 2 && (
            <button
              className="action-btn"
              onClick={() => setCollapsed(prev => ({ ...prev, [tier]: !prev[tier] }))}
              style={{ fontSize: 11, padding: '2px 8px' }}
            >
              {isCollapsed ? '展开全部' : '折叠'}
            </button>
          )}
        </div>
        {displayTags.map(renderTagCard)}
        {hasMore && (
          <div style={{ textAlign: 'center', color: '#666', fontSize: 12, padding: 4 }}>
            还有 {sectionTags.length - 2} 个...
          </div>
        )}
      </div>
    )
  }

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>
        <NavBar />
        <p style={{ marginTop: 40 }}>加载中...</p>
      </div>
    )
  }

  return (
    <div style={{ padding: '0 12px', maxWidth: 800, margin: '0 auto' }}>
      <NavBar />

      <div className="section" style={{ marginTop: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <h2 style={{ margin: 0, color: '#eee', fontSize: 16 }}>💡 最强逻辑追踪</h2>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="action-btn" onClick={openNew} style={{ fontSize: 12 }}>
              + 新建逻辑
            </button>
            <button className="action-btn" onClick={openForecast} style={{ fontSize: 12 }}>
              📅 事件日历
            </button>
          </div>
        </div>
      </div>

      {/* ── Feed Section ── */}
      <div className="section" style={{ marginTop: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <h2 style={{ margin: 0, color: '#eee', fontSize: 16 }}>📤 投喂资料</h2>
        </div>

        {/* Single input bar */}
        {!feedResult && (
          <div>
            <div style={{ display: 'flex', gap: 6 }}>
              <div style={{ flex: 1, position: 'relative' }}>
                <input
                  value={feedUrl}
                  onChange={e => setFeedUrl(e.target.value)}
                  placeholder="粘贴链接或上传文件..."
                  style={{ width: '100%', padding: '6px 8px', background: '#1a1a2e', border: '1px solid #333', color: '#eee', borderRadius: 4, fontSize: 13 }}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && feedUrl.trim()) {
                      // Auto-detect from URL
                      const url = feedUrl.trim()
                      if (url.includes('mp.weixin.qq.com')) {
                        setFeedTab('wechat')
                      } else if (url.includes('douyin.com')) {
                        setFeedTab('douyin')
                      } else if (url.endsWith('.pdf')) {
                        setFeedTab('report')
                      }
                      handleFeedProcess()
                    }
                  }}
                />
                {/* Auto-detect badge */}
                {feedUrl.includes('mp.weixin.qq.com') && (
                  <span style={{ position: 'absolute', right: 6, top: 5, fontSize: 10, padding: '1px 6px', borderRadius: 3, background: '#4ecdc422', color: '#4ecdc4' }}>
                    📱 公众号
                  </span>
                )}
                {feedUrl.includes('douyin.com') && (
                  <span style={{ position: 'absolute', right: 6, top: 5, fontSize: 10, padding: '1px 6px', borderRadius: 3, background: '#f59e0b22', color: '#f59e0b' }}>
                    🎬 抖音
                  </span>
                )}
                {feedUrl.endsWith('.pdf') && (
                  <span style={{ position: 'absolute', right: 6, top: 5, fontSize: 10, padding: '1px 6px', borderRadius: 3, background: '#e9456022', color: '#e94560' }}>
                    📄 研报
                  </span>
                )}
              </div>
              <button className="action-btn" onClick={() => document.getElementById('pdf-upload-inline')?.click()}
                style={{ fontSize: 11, background: '#1a1a2e', color: '#888', border: '1px solid #333', padding: '5px 10px' }}>
                📎
              </button>
              <input type="file" accept=".pdf" onChange={e => {
                const f = e.target.files?.[0]
                if (f) { setPdfFile(f); setFeedTab('report') }
              }} style={{ display: 'none' }} id="pdf-upload-inline" />
            </div>
            {feedError && <div style={{ color: '#e94560', fontSize: 11, marginTop: 6 }}>{feedError}</div>}
          </div>
        )}

        {/* Loading */}
        {feedLoading && (
          <div style={{ textAlign: 'center', color: '#666', fontSize: 12, padding: 12 }}>
            处理中...
          </div>
        )}

        {/* RESULT: after processing */}
        {feedResult && (
          <div className="info-card" style={{ padding: 10, marginTop: 4 }}>
            {/* Source badges */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 6, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 3, background: '#1a1a2e', color: '#4ecdc4', border: '1px solid #4ecdc444' }}>
                {feedTab === 'wechat' ? '📱 公众号' : feedTab === 'report' ? '📄 研报' : '🎬 抖音'}
              </span>
              <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 3, background: '#1a1a2e', color: '#f59e0b' }}>
                {feedResult.source_name}
              </span>
              <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 3, background: '#1a1a2e', color: '#aaa' }}>
                {feedResult.llm_used ? '🤖 AI辅助' : '🔍 关键词'}
              </span>
            </div>

            {/* Title */}
            <div style={{ color: '#eee', fontSize: 14, fontWeight: 'bold', marginBottom: 8, lineHeight: 1.3 }}>
              {feedResult.title || '-'}
            </div>

            {/* Summary + Core Logic + Tags in compact layout */}
            <div className="info-card" style={{ padding: 8, marginBottom: 6, borderLeft: '3px solid #4ecdc4' }}>
              <div style={{ color: '#4ecdc4', fontSize: 10, marginBottom: 3 }}>📝 摘要</div>
              <div style={{ color: '#ccc', fontSize: 11, lineHeight: 1.4 }}>{feedResult.summary || '-'}</div>
            </div>

            <div className="info-card" style={{ padding: 8, marginBottom: 6, borderLeft: '3px solid #e94560' }}>
              <div style={{ color: '#e94560', fontSize: 10, marginBottom: 3 }}>🎯 核心逻辑</div>
              <div style={{ color: '#eee', fontSize: 11, lineHeight: 1.4 }}>{feedResult.core_logic || '（未提取到核心逻辑）'}</div>
            </div>

            {/* Tags */}
            <div style={{ marginBottom: 8 }}>
              <label style={{ color: '#888', fontSize: 10, display: 'block', marginBottom: 3 }}>匹配标签（可修改）</label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {tags.map(t => {
                  const isSelected = feedSelected.includes(t.id)
                  const recommended = feedResult.recommended_tags?.find((r: any) => r.tag_id === t.id)
                  return (
                    <label key={t.id} style={{
                      display: 'flex', alignItems: 'center', gap: 3,
                      padding: '2px 6px', borderRadius: 3, fontSize: 11, cursor: 'pointer',
                      background: isSelected ? '#4ecdc422' : '#1a1a2e',
                      border: isSelected ? '1px solid #4ecdc4' : '1px solid #333',
                      color: isSelected ? '#4ecdc4' : '#888',
                    }}>
                      <input type="checkbox" checked={isSelected}
                        onChange={() => setFeedSelected(prev =>
                          prev.includes(t.id) ? prev.filter(id => id !== t.id) : [...prev, t.id]
                        )} style={{ accentColor: '#4ecdc4', width: 11, height: 11 }} />
                      {t.name}
                      {recommended && <span style={{ color: '#aaa', fontSize: 9 }}>({recommended.confidence}分)</span>}
                    </label>
                  )
                })}
                {tags.length === 0 && <div style={{ color: '#666', fontSize: 11 }}>暂无标签，先创建逻辑标签</div>}
              </div>
            </div>

            {/* Suggested New Tags */}
            {feedResult.suggested_new_tags && feedResult.suggested_new_tags.length > 0 && (
              <div className="info-card" style={{ padding: 8, marginBottom: 8, borderLeft: '3px solid #f59e0b' }}>
                <div style={{ color: '#f59e0b', fontSize: 10, marginBottom: 4 }}>💡 建议新建逻辑</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {feedResult.suggested_new_tags.map((st: any, i: number) => (
                    <div key={i} style={{ padding: '4px 8px', borderRadius: 3, fontSize: 11, background: '#1a1a2e', color: '#f59e0b', border: '1px solid #f59e0b44' }}>
                      <div style={{ fontWeight: 'bold' }}>🏷️ {st.name}</div>
                      <div style={{ color: '#aaa', fontSize: 10, marginTop: 2 }}>{st.description}</div>
                      {st.industries && st.industries.length > 0 && (
                        <div style={{ color: '#888', fontSize: 9, marginTop: 2 }}>行业: {st.industries.join('、')}</div>
                      )}
                      {st.related_stocks && st.related_stocks.length > 0 && (
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2, marginTop: 2 }}>
                          {st.related_stocks.map((s: any, j: number) => {
                            const code = typeof s === 'string' ? s : s.code
                            const name = typeof s === 'string' ? '' : s.name || ''
                            return (
                              <span key={j} style={{ fontSize: 9, padding: '1px 5px', borderRadius: 2, background: '#4ecdc422', color: '#4ecdc4' }}>
                                📈 {name && `${name}(${code})`}{!name && code}
                              </span>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
                <div style={{ fontSize: 10, color: '#666', marginTop: 4 }}>
                  可在「+ 新建逻辑」中创建这些标签
                </div>
              </div>
            )}

            {feedError && <div style={{ color: '#e94560', fontSize: 11, marginBottom: 6 }}>{feedError}</div>}

            <div style={{ display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
              <button className="action-btn" onClick={() => { setFeedResult(null); setFeedUrl(''); setFeedError(''); }}
                style={{ fontSize: 11, padding: '3px 10px', color: '#888' }}>
                取消
              </button>
              <button className="action-btn" onClick={handleFeedSave}
                style={{ fontSize: 11, padding: '3px 10px', background: '#4ecdc4', color: '#111' }}>
                确认保存
              </button>
            </div>
          </div>
        )}
      </div>

      {tags.length === 0 ? (
        <div className="info-card" style={{ textAlign: 'center', padding: 30, color: '#666', marginTop: 12 }}>
          <p style={{ fontSize: 14 }}>暂无逻辑标签</p>
          <p style={{ fontSize: 12 }}>点击「+ 新建逻辑」开始追踪市场最强逻辑</p>
        </div>
      ) : (
        <>
          {/* Search */}
          <div style={{ marginBottom: 10 }}>
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="🔍 搜索逻辑标签..."
              style={{ width: '100%', padding: '6px 10px', background: '#1a1a2e', border: '1px solid #333', color: '#eee', borderRadius: 4, fontSize: 13 }}
            />
          </div>
          {renderSection('focused', '🌟 聚焦（' + Math.min(tags.filter(t => t.tier === 'focused').length, 3) + '/3）')}
          {renderSection('core', '📌 核心')}
          {renderSection('watch', '👁️ 观察')}
        </>
      )}

      {/* ── Logic Graph (collapsible) ── */}
      {entries.length > 0 && (
        <div className="section" style={{ marginTop: 12 }}>
          <div
            onClick={() => setShowGraph(!showGraph)}
            style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer', userSelect: 'none' }}
          >
            <h2 style={{ margin: 0, color: '#eee', fontSize: 16 }}>🧠 逻辑图谱（{entries.length} 条投喂）</h2>
            <span style={{ color: '#888', fontSize: 12 }}>{showGraph ? '▲ 收起' : '▼ 展开'}</span>
          </div>
          {showGraph && (() => {
          // ── Graph data ──
          interface GraphNode { id: string; type: 'logic' | 'industry' | 'stock' | 'entry'; label: string; }
          interface GraphEdge { source: string; target: string; }

          const nodeMap = new Map<string, GraphNode>()
          const edgeSet = new Set<string>() // "source->target"

          const addNode = (id: string, type: GraphNode['type'], label: string) => {
            if (!nodeMap.has(id)) nodeMap.set(id, { id, type, label })
          }
          const addEdge = (s: string, t: string) => {
            const key = s < t ? `${s}->${t}` : `${t}->${s}`
            edgeSet.add(key)
          }

          for (const e of entries) {
            const eId = `entry:${e.id}`
            addNode(eId, 'entry', e.title || 'Untitled')
            const inds: string[] = e.industries || []
            const logics: string[] = e.extracted_logics || []
            const stocks: { code: string; name: string }[] = e.companies || []

            for (const ind of inds) {
              const nId = `industry:${ind}`
              addNode(nId, 'industry', ind)
              addEdge(eId, nId)
            }
            for (const l of logics) {
              const nId = `logic:${l}`
              addNode(nId, 'logic', l)
              addEdge(eId, nId)
            }
            for (const s of stocks) {
              const code = typeof s === 'string' ? s : s.code
              const name = typeof s === 'string' ? '' : s.name || ''
              const nId = `stock:${code}`
              const label = name ? `${name}(${code})` : code
              addNode(nId, 'stock', label)
              addEdge(eId, nId)
              // Logic ↔ Stock
              for (const l of logics) {
                addEdge(`logic:${l}`, nId)
              }
              // Industry ↔ Stock
              for (const ind of inds) {
                addEdge(`industry:${ind}`, nId)
              }
            }
            // Logic ↔ Industry
            for (const l of logics) {
              for (const ind of inds) {
                addEdge(`logic:${l}`, `industry:${ind}`)
              }
            }
          }

          const nodes = Array.from(nodeMap.values())
          const edges = Array.from(edgeSet).map(k => {
            const [a, b] = k.split('->')
            return { source: a, target: b } as GraphEdge
          })

          // ── Position calculation ──
          const COL_W = 320
          const ROW_H = 90
          const ENTRY_Y_OFFSET = 60

          const logicNodes = nodes.filter(n => n.type === 'logic')
          const industryNodes = nodes.filter(n => n.type === 'industry')
          const stockNodes = nodes.filter(n => n.type === 'stock')
          const entryNodes = nodes.filter(n => n.type === 'entry')

          const positions: Record<string, { x: number; y: number }> = {}

          const maxRows = Math.max(logicNodes.length, industryNodes.length, stockNodes.length)
          const entryStartY = maxRows * ROW_H + 120 + ENTRY_Y_OFFSET

          industryNodes.forEach((n, i) => { positions[n.id] = { x: 0, y: i * ROW_H + 20 } })
          logicNodes.forEach((n, i) => { positions[n.id] = { x: COL_W, y: i * ROW_H + 20 } })
          stockNodes.forEach((n, i) => { positions[n.id] = { x: COL_W * 2, y: i * ROW_H + 20 } })
          entryNodes.forEach((n, i) => { positions[n.id] = { x: COL_W, y: entryStartY + i * ROW_H } })

          // ── Node dimensions for edge endpoint calcs ──
          const nodeWidth: Record<string, number> = {}
          nodes.forEach(n => {
            if (n.type === 'entry') nodeWidth[n.id] = 280
            else if (n.type === 'logic') nodeWidth[n.id] = 280
            else if (n.type === 'industry') nodeWidth[n.id] = 200
            else nodeWidth[n.id] = 220
          })
          const nodeHeight = 28

          // ── Selection state ──

          const getConnectedNodeIds = (nodeId: string): Set<string> => {
            const connected = new Set<string>([nodeId])
            for (const edge of edges) {
              if (edge.source === nodeId) connected.add(edge.target)
              if (edge.target === nodeId) connected.add(edge.source)
            }
            return connected
          }

          const isConnected = (nodeId: string, selectedId: string): boolean => {
            if (nodeId === selectedId) return true
            for (const edge of edges) {
              if ((edge.source === nodeId && edge.target === selectedId) ||
                  (edge.target === nodeId && edge.source === selectedId)) return true
            }
            return false
          }

          const graphWidth = COL_W * 2 + 280
          const graphHeight = entryStartY + entryNodes.length * ROW_H + 60

          return (
            <div style={{ marginTop: 4, background: '#0d0d1a', borderRadius: 8, padding: 8, overflow: 'auto', maxHeight: 'calc(100vh - 280px)' }}>
              <div style={{ position: 'relative', width: graphWidth, height: graphHeight, minWidth: graphWidth, minHeight: graphHeight }}>
                {/* SVG layer for edges */}
                <svg width={graphWidth} height={graphHeight} style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none', zIndex: 0 }}>
                  {edges.map((edge, idx) => {
                    const sp = positions[edge.source]
                    const tp = positions[edge.target]
                    if (!sp || !tp) return null
                    const sw = nodeWidth[edge.source] || 200
                    const tw = nodeWidth[edge.target] || 200
                    const x1 = sp.x + sw / 2
                    const y1 = sp.y + nodeHeight / 2
                    const x2 = tp.x + tw / 2
                    const y2 = tp.y + nodeHeight / 2

                    let dimmed = false
                    if (selectedNode !== null) {
                      const srcConnected = isConnected(edge.source, selectedNode)
                      const tgtConnected = isConnected(edge.target, selectedNode)
                      dimmed = !(srcConnected && tgtConnected)
                    }

                    return (
                      <line
                        key={idx}
                        x1={x1} y1={y1} x2={x2} y2={y2}
                        stroke={dimmed ? '#ffffff11' : selectedNode ? '#ffffff66' : '#ffffff33'}
                        strokeWidth={dimmed ? 0.5 : selectedNode ? 2 : 1}
                      />
                    )
                  })}
                </svg>

                {/* Node layer */}
                {nodes.map(n => {
                  const pos = positions[n.id]
                  if (!pos) return null
                  const isSelected = selectedNode === n.id
                  const connectedNodes = selectedNode ? getConnectedNodeIds(selectedNode) : null
                  const isDimmed = selectedNode !== null && !connectedNodes!.has(n.id)

                  let bgColor = '#888'
                  let borderColor = '#888'
                  if (n.type === 'logic') { bgColor = '#f59e0b22'; borderColor = '#f59e0b' }
                  else if (n.type === 'industry') { bgColor = '#4ecdc422'; borderColor = '#4ecdc4' }
                  else if (n.type === 'stock') { bgColor = '#4ecdc422'; borderColor = '#4ecdc4' }
                  else { bgColor = '#444422'; borderColor = '#888' }

                  const dotColor = n.type === 'logic' ? '#f59e0b' : n.type === 'entry' ? '#888' : '#4ecdc4'

                  const maxLabelLen = n.type === 'entry' ? 28 : n.type === 'logic' ? 30 : 20
                  const displayLabel = n.label.length > maxLabelLen ? n.label.slice(0, maxLabelLen) + '...' : n.label

                  return (
                    <div
                      key={n.id}
                      onClick={() => setSelectedNode(isSelected ? null : n.id)}
                      style={{
                        position: 'absolute',
                        left: pos.x,
                        top: pos.y,
                        width: nodeWidth[n.id],
                        height: nodeHeight,
                        background: isDimmed ? '#1a1a2e44' : bgColor,
                        border: `1px solid ${isDimmed ? '#333' : isSelected ? borderColor : borderColor + '66'}`,
                        borderRadius: 6,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0 6px 0 8px',
                        cursor: 'pointer',
                        zIndex: isSelected ? 10 : 1,
                        opacity: isDimmed ? 0.3 : 1,
                        transition: 'opacity 0.2s, border-color 0.2s',
                        boxSizing: 'border-box',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        boxShadow: isSelected ? `0 0 12px ${dotColor}66` : 'none',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4, overflow: 'hidden', flex: 1 }}>
                        <span style={{ width: 8, height: 8, borderRadius: '50%', background: dotColor, flexShrink: 0 }} />
                        <span style={{ fontSize: 11, color: isDimmed ? '#666' : isSelected ? '#fff' : '#ddd', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {displayLabel}
                        </span>
                      </div>
                      {n.type === 'entry' && (
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDeleteEntry(n.id.replace('entry:', '')) }}
                          style={{
                            background: 'none', border: 'none', color: '#e94560', cursor: 'pointer',
                            fontSize: 10, padding: '0 2px', flexShrink: 0, lineHeight: 1,
                            opacity: isDimmed ? 0.3 : 0.7,
                          }}
                          title="删除"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  )
                })}

                {/* Column labels */}
                {industryNodes.length > 0 && (
                  <div style={{ position: 'absolute', left: 0, top: -2, fontSize: 10, color: '#4ecdc4', opacity: 0.6, fontWeight: 'bold' }}>🏭 行业</div>
                )}
                {logicNodes.length > 0 && (
                  <div style={{ position: 'absolute', left: COL_W, top: -2, fontSize: 10, color: '#f59e0b', opacity: 0.6, fontWeight: 'bold' }}>🧠 逻辑</div>
                )}
                {stockNodes.length > 0 && (
                  <div style={{ position: 'absolute', left: COL_W * 2, top: -2, fontSize: 10, color: '#4ecdc4', opacity: 0.6, fontWeight: 'bold' }}>📈 个股</div>
                )}
              </div>
            </div>
          )})()}
        </div>
      )}

      {/* Form Modal */}
      {showForm && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          backgroundColor: 'rgba(0,0,0,0.7)',
        }} onClick={() => setShowForm(false)}>
          <div className="info-card" style={{
            width: 400, maxWidth: '90vw', padding: 20,
          }} onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 12px', color: '#eee', fontSize: 15 }}>
              {editing ? '编辑逻辑标签' : '新建逻辑标签'}
            </h3>

            <div style={{ marginBottom: 10 }}>
              <label style={{ color: '#888', fontSize: 11, display: 'block', marginBottom: 3 }}>ID *</label>
              <input
                value={form.id}
                onChange={e => setForm(f => ({ ...f, id: e.target.value }))}
                disabled={!!editing}
                placeholder="唯一标识：tag-xxx"
                style={{ width: '100%', padding: '6px 8px', background: '#1a1a2e', border: '1px solid #333', color: '#eee', borderRadius: 4, fontSize: 13 }}
              />
            </div>

            <div style={{ marginBottom: 10 }}>
              <label style={{ color: '#888', fontSize: 11, display: 'block', marginBottom: 3 }}>名称 *</label>
              <input
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder="如：AI算力链条"
                style={{ width: '100%', padding: '6px 8px', background: '#1a1a2e', border: '1px solid #333', color: '#eee', borderRadius: 4, fontSize: 13 }}
              />
            </div>

            <div style={{ marginBottom: 10 }}>
              <label style={{ color: '#888', fontSize: 11, display: 'block', marginBottom: 3 }}>描述</label>
              <textarea
                value={form.description}
                onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                placeholder="对这个逻辑的简要说明"
                rows={2}
                style={{ width: '100%', padding: '6px 8px', background: '#1a1a2e', border: '1px solid #333', color: '#eee', borderRadius: 4, fontSize: 13, resize: 'vertical' }}
              />
            </div>

            <div style={{ marginBottom: 10 }}>
              <label style={{ color: '#888', fontSize: 11, display: 'block', marginBottom: 3 }}>层级</label>
              <select
                value={form.tier}
                onChange={e => setForm(f => ({ ...f, tier: e.target.value as any }))}
                style={{ width: '100%', padding: '6px 8px', background: '#1a1a2e', border: '1px solid #333', color: '#eee', borderRadius: 4, fontSize: 13 }}
              >
                <option value="watch">👁️ 观察</option>
                <option value="core">📌 核心</option>
                <option value="focused">🌟 聚焦</option>
              </select>
            </div>

            <div style={{ marginBottom: 10 }}>
              <label style={{ color: '#888', fontSize: 11, display: 'block', marginBottom: 3 }}>关联行业（逗号分隔）</label>
              <input
                value={form.related_industries}
                onChange={e => setForm(f => ({ ...f, related_industries: e.target.value }))}
                placeholder="半导体,光模块,PCB"
                style={{ width: '100%', padding: '6px 8px', background: '#1a1a2e', border: '1px solid #333', color: '#eee', borderRadius: 4, fontSize: 13 }}
              />
            </div>

            <div style={{ marginBottom: 14 }}>
              <label style={{ color: '#888', fontSize: 11, display: 'block', marginBottom: 3 }}>关联个股（逗号分隔）</label>
              <input
                value={form.related_stocks}
                onChange={e => setForm(f => ({ ...f, related_stocks: e.target.value }))}
                placeholder="300502,002916,600584"
                style={{ width: '100%', padding: '6px 8px', background: '#1a1a2e', border: '1px solid #333', color: '#eee', borderRadius: 4, fontSize: 13 }}
              />
            </div>

            {error && (
              <div style={{ color: '#e94560', fontSize: 12, marginBottom: 8 }}>{error}</div>
            )}

            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="action-btn" onClick={() => setShowForm(false)} style={{ fontSize: 12 }}>
                取消
              </button>
              <button className="action-btn" onClick={handleSave} style={{ fontSize: 12, background: '#4ecdc4', color: '#111' }}>
                {editing ? '保存修改' : '创建'}
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Forecast Modal */}
      {showForecast && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, zIndex: 9999,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          backgroundColor: 'rgba(0,0,0,0.7)',
        }} onClick={() => setShowForecast(false)}>
          <div className="info-card" style={{ width: 450, maxWidth: '90vw', padding: 20, maxHeight: '80vh', overflow: 'auto' }}
            onClick={e => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 12px', color: '#eee', fontSize: 15 }}>📅 前置预判</h3>
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <button className="action-btn" onClick={() => setFcTab('list')}
                style={{ fontSize: 12, background: fcTab === 'list' ? '#4ecdc4' : '#1a1a2e', color: fcTab === 'list' ? '#111' : '#888' }}>事件列表</button>
              <button className="action-btn" onClick={() => setFcTab('add')}
                style={{ fontSize: 12, background: fcTab === 'add' ? '#4ecdc4' : '#1a1a2e', color: fcTab === 'add' ? '#111' : '#888' }}>+ 新建</button>
            </div>

            {fcTab === 'list' ? (
              <>
                {forecasts.length === 0 ? (
                  <div style={{ color: '#666', fontSize: 13, textAlign: 'center', padding: 20 }}>未来30天无预判事件</div>
                ) : (
                  forecasts.map((f: any) => (
                    <div key={f.id} className="info-card" style={{ padding: 10, marginBottom: 6, borderLeft: '3px solid #f59e0b' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: '#f59e0b', fontSize: 12 }}>{f.event_date}</span>
                        <button className="action-btn" onClick={() => handleDeleteForecast(f.id)}
                          style={{ fontSize: 10, padding: '1px 6px', color: '#e94560' }}>删除</button>
                      </div>
                      <div style={{ color: '#eee', fontSize: 13 }}>{f.title}</div>
                      {f.prediction && <div style={{ color: '#aaa', fontSize: 11, marginTop: 2 }}>预判：{f.prediction}</div>}
                      {f.logic_tags?.length > 0 && (
                        <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
                          {f.logic_tags.map((t: string) => (
                            <span key={t} style={{ fontSize: 10, padding: '1px 6px', background: '#1a1a2e', borderRadius: 3, color: '#888' }}>{t}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}
              </>
            ) : (
              <>
                <div style={{ marginBottom: 8 }}>
                  <label style={{ color: '#888', fontSize: 11, display: 'block', marginBottom: 3 }}>事件名称 *</label>
                  <input value={fcForm.title} onChange={e => setFcForm(f => ({ ...f, title: e.target.value }))}
                    placeholder="英伟达FY26Q2财报" style={{ width: '100%', padding: '6px 8px', background: '#1a1a2e', border: '1px solid #333', color: '#eee', borderRadius: 4, fontSize: 13 }} />
                </div>
                <div style={{ marginBottom: 8 }}>
                  <label style={{ color: '#888', fontSize: 11, display: 'block', marginBottom: 3 }}>事件日期 *</label>
                  <input type="date" value={fcForm.event_date} onChange={e => setFcForm(f => ({ ...f, event_date: e.target.value }))}
                    style={{ width: '100%', padding: '6px 8px', background: '#1a1a2e', border: '1px solid #333', color: '#eee', borderRadius: 4, fontSize: 13 }} />
                </div>
                <div style={{ marginBottom: 8 }}>
                  <label style={{ color: '#888', fontSize: 11, display: 'block', marginBottom: 3 }}>你的预判</label>
                  <input value={fcForm.prediction} onChange={e => setFcForm(f => ({ ...f, prediction: e.target.value }))}
                    placeholder="超预期→光模块受益" style={{ width: '100%', padding: '6px 8px', background: '#1a1a2e', border: '1px solid #333', color: '#eee', borderRadius: 4, fontSize: 13 }} />
                </div>
                <div style={{ marginBottom: 12 }}>
                  <label style={{ color: '#888', fontSize: 11, display: 'block', marginBottom: 3 }}>关联逻辑标签ID（逗号分隔）</label>
                  <input value={fcForm.logic_tags} onChange={e => setFcForm(f => ({ ...f, logic_tags: e.target.value }))}
                    placeholder="tag-ai-chain,tag-pkg" style={{ width: '100%', padding: '6px 8px', background: '#1a1a2e', border: '1px solid #333', color: '#eee', borderRadius: 4, fontSize: 13 }} />
                </div>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button className="action-btn" onClick={() => setShowForecast(false)} style={{ fontSize: 12 }}>关闭</button>
                  <button className="action-btn" onClick={handleAddForecast}
                    style={{ fontSize: 12, background: '#4ecdc4', color: '#111' }}>保存预判</button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
