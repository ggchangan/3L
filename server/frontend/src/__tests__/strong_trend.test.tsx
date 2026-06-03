import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import StrongTrendCandidates from '../pages/StrongTrendCandidates'

function renderPage() {
  return render(<MemoryRouter><StrongTrendCandidates /></MemoryRouter>)
}

describe('StrongTrendCandidatesPage', () => {
  it('渲染标题', () => {
    renderPage()
    const els = screen.getAllByText('📈 强势趋势追踪')
    expect(els.length).toBeGreaterThanOrEqual(1)
  })

  it('渲染副标题', () => {
    renderPage()
    expect(screen.getByText('从强势板块筛选趋势完好的个股')).toBeTruthy()
  })

  it('渲染加载状态', () => {
    renderPage()
    expect(screen.getByText('加载中...')).toBeTruthy()
  })

  it('页面容器使用 page-container', () => {
    renderPage()
    expect(document.querySelector('.page-container')).toBeTruthy()
  })

  it('渲染底部footer', () => {
    renderPage()
    expect(screen.getByText('3L 交易体系 · 强势趋势追踪 · Hermes Agent')).toBeTruthy()
  })
})
