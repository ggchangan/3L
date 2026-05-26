import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Industry from '../pages/Industry'

function renderPage() {
  return render(<MemoryRouter><Industry /></MemoryRouter>)
}

describe('IndustryPage', () => {
  it('渲染标题', () => {
    renderPage()
    const els = screen.getAllByText('🔬 行业追踪')
    expect(els.length).toBeGreaterThanOrEqual(1)
  })

  it('渲染副标题', () => {
    renderPage()
    expect(screen.getByText('公司分析 · 行业研究 · 机构研报')).toBeTruthy()
  })

  it('渲染加载区域', () => {
    renderPage()
    // 加载时显示 spinner
    expect(document.querySelector('.loading-area')).toBeTruthy()
    expect(document.querySelector('.spinner')).toBeTruthy()
  })

  it('加载时Tab容器不显示', () => {
    renderPage()
    expect(document.querySelector('.cat-tabs')).toBeFalsy()
  })

  it('渲染底部footer', () => {
    renderPage()
    expect(screen.getByText('3L 交易体系 · 行业追踪知识库')).toBeTruthy()
  })

  it('页面容器使用 page-container', () => {
    renderPage()
    expect(document.querySelector('.page-container')).toBeTruthy()
  })
})
