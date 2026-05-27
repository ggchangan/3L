import { useState, useEffect } from 'react'
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

  useEffect(() => { fetchTags() }, [])

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

  const renderTagCard = (tag: LogicTag) => (
    <div key={tag.id} className="info-card" style={{ marginBottom: 8, padding: 10, position: 'relative' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ fontWeight: 'bold', color: COLORS[tag.tier] || '#eee' }}>
          {tag.name}
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="action-btn" onClick={() => openEdit(tag)} style={{ fontSize: 11, padding: '2px 6px' }}>
            编辑
          </button>
          <button className="action-btn" onClick={() => handleDelete(tag.id)} style={{ fontSize: 11, padding: '2px 6px', color: '#e94560' }}>
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
            <button className="action-btn" style={{ fontSize: 12 }}>
              📤 投喂
            </button>
          </div>
        </div>
      </div>

      {tags.length === 0 ? (
        <div className="info-card" style={{ textAlign: 'center', padding: 30, color: '#666', marginTop: 12 }}>
          <p style={{ fontSize: 14 }}>暂无逻辑标签</p>
          <p style={{ fontSize: 12 }}>点击「+ 新建逻辑」开始追踪市场最强逻辑</p>
        </div>
      ) : (
        <>
          {renderSection('focused', '🌟 聚焦（' + Math.min(tags.filter(t => t.tier === 'focused').length, 3) + '/3）')}
          {renderSection('core', '📌 核心')}
          {renderSection('watch', '👁️ 观察')}
        </>
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
    </div>
  )
}
