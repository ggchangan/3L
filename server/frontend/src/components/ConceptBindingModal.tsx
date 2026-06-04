import { useState, useEffect, useRef, useCallback } from 'react'

interface ConceptResult {
  code: string
  name: string
}

interface Props {
  /** 细分方向完整名，如 "科技.半导体" */
  subDir: string
  /** 当前已绑定的概念代码列表 */
  boundCodes: string[]
  /** 关闭弹窗 */
  onClose: () => void
  /** 保存成功后回调（用于刷新父组件数据） */
  onSaved: () => void
}

export default function ConceptBindingModal({ subDir, boundCodes, onClose, onSaved }: Props) {
  const [searchQ, setSearchQ] = useState('')
  const [results, setResults] = useState<ConceptResult[]>([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(new Set(boundCodes))
  const [saving, setSaving] = useState(false)
  const searchTimer = useRef<ReturnType<typeof setTimeout>>()
  const inputRef = useRef<HTMLInputElement>(null)

  // 初始化选中状态
  useEffect(() => {
    setSelected(new Set(boundCodes))
  }, [boundCodes])

  // 聚焦搜索框
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // 实时搜索
  useEffect(() => {
    clearTimeout(searchTimer.current)
    if (!searchQ || searchQ.length < 1) {
      setResults([])
      setLoading(false)
      return
    }
    setLoading(true)
    searchTimer.current = setTimeout(async () => {
      try {
        const r = await fetch(`/api/directions/concepts/search?q=${encodeURIComponent(searchQ)}`)
        const data = await r.json()
        setResults(data.results || data || [])
      } catch {
        setResults([])
      }
      setLoading(false)
    }, 300)
    return () => clearTimeout(searchTimer.current)
  }, [searchQ])

  function toggleConcept(code: string) {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  // 计算差异：新选的 vs 新取消的
  async function handleSave() {
    if (saving) return
    setSaving(true)
    const origSet = new Set(boundCodes)
    const toBind = [...selected].filter(c => !origSet.has(c))
    const toUnbind = [...origSet].filter(c => !selected.has(c))
    try {
      // 并发绑定/解绑
      const ops: Promise<Response>[] = [
        ...toBind.map(code =>
          fetch('/api/directions/bind', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sub_dir: subDir, concept_code: code }),
          })
        ),
        ...toUnbind.map(code =>
          fetch('/api/directions/unbind', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sub_dir: subDir, concept_code: code }),
          })
        ),
      ]
      if (ops.length === 0) {
        showToast('没有变化')
        setSaving(false)
        return
      }
      const responses = await Promise.all(ops)
      const allOk = responses.every(r => r.ok)
      if (allOk) {
        showToast(`✅ 已保存概念绑定（${toBind.length} 绑定, ${toUnbind.length} 解绑）`)
        onSaved()
        onClose()
      } else {
        showToast('⚠️ 部分操作失败', true)
      }
    } catch {
      showToast('⚠️ 保存失败', true)
    }
    setSaving(false)
  }

  function showToast(msg: string, isError?: boolean) {
    const el = document.createElement('div')
    el.textContent = msg
    el.className = 'toast'
    el.style.cssText = `position:fixed;bottom:30px;left:50%;transform:translate(-50%);background:#1a1a2e;border:1px solid ${isError ? '#e94560' : '#22c55e'};color:${isError ? '#e94560' : '#22c55e'};padding:8px 20px;border-radius:6px;font-size:13px;z-index:999;transition:opacity .3s`
    document.body.appendChild(el)
    setTimeout(() => { el.style.opacity = '0'; setTimeout(() => el.remove(), 300) }, 2000)
  }

  // 根据搜索结果和已选状态排序：已选的排在前面
  const sortedResults = [...results].sort((a, b) => {
    const aSel = selected.has(a.code) ? 0 : 1
    const bSel = selected.has(b.code) ? 0 : 1
    if (aSel !== bSel) return aSel - bSel
    return 0
  })

  // 如果没有搜索词，展示所有已绑定的概念
  const displayList = searchQ.trim() ? sortedResults : results.length > 0 ? sortedResults : []

  return (
    <div className="concept-modal-overlay" onClick={onClose}>
      <div className="concept-modal" onClick={e => e.stopPropagation()}>
        <div className="concept-modal-header">
          <span>🎯 绑定概念 — {subDir}</span>
          <button className="concept-modal-close" onClick={onClose}>&times;</button>
        </div>

        <div className="concept-modal-search">
          <input
            ref={inputRef}
            className="search-input"
            placeholder="搜索同花顺概念板块..."
            value={searchQ}
            onChange={e => setSearchQ(e.target.value)}
          />
          {loading && <span className="concept-search-spinner">⏳</span>}
        </div>

        <div className="concept-modal-list">
          {!searchQ.trim() && boundCodes.length > 0 && (
            <div className="concept-modal-hint">已绑定 {boundCodes.length} 个概念（继续搜索添加更多）</div>
          )}
          {displayList.length === 0 && !loading && (
            <div className="concept-modal-empty">
              {searchQ.trim() ? '无匹配概念' : '输入关键词搜索概念板块'}
            </div>
          )}
          {displayList.map(item => {
            const isSelected = selected.has(item.code)
            return (
              <label
                key={item.code}
                className={`concept-modal-item ${isSelected ? 'selected' : ''}`}
                onClick={() => toggleConcept(item.code)}
              >
                <div className="concept-item-left">
                  <input
                    type="checkbox"
                    className="concept-item-cb"
                    checked={isSelected}
                    readOnly
                  />
                  <span className="concept-item-name">{item.name}</span>
                </div>
              </label>
            )
          })}
        </div>

        <div className="concept-modal-footer">
          <span className="concept-modal-count">已选 {selected.size} 个概念</span>
          <button
            className="btn btn-green btn-sm"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}
