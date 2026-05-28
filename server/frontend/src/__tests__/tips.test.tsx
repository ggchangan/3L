import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Tips from '../pages/Tips'

function renderPage() {
  return render(<MemoryRouter><Tips /></MemoryRouter>)
}

describe('TipsPage', () => {
  it('渲染标题', () => {
    renderPage()
    const els = screen.getAllByText('📝 交易技巧')
    expect(els.length).toBeGreaterThanOrEqual(1)
  })

  it('渲染副标题', () => {
    renderPage()
    expect(screen.getByText('简放公众号文章 · 持续收录中')).toBeTruthy()
  })

  it('渲染加载状态', () => {
    renderPage()
    expect(document.querySelector('.spinner')).toBeTruthy()
  })

  it('渲染底部footer', () => {
    renderPage()
    expect(screen.getByText('3L 交易体系 · 交易技巧知识库')).toBeTruthy()
  })

  it('加载时不显示卡片网格', () => {
    renderPage()
    expect(document.querySelector('.tips-grid')).toBeFalsy()
  })

  it('页面容器使用 page-container', () => {
    renderPage()
    expect(document.querySelector('.page-container')).toBeTruthy()
  })
})
