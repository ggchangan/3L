import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import TopGainers from '../pages/TopGainers'

function renderPage() {
  return render(<MemoryRouter><TopGainers /></MemoryRouter>)
}

describe('TopGainersPage', () => {
  it('渲染标题', () => {
    renderPage()
    const els = screen.getAllByText('📈 30日涨幅榜')
    expect(els.length).toBeGreaterThanOrEqual(1)
  })

  it('渲染副标题', () => {
    renderPage()
    expect(screen.getByText('全市场个股 · 近30日涨幅排序 · 板块分布')).toBeTruthy()
  })

  it('渲染控制栏', () => {
    renderPage()
    expect(screen.getByText('📅 截止日期')).toBeTruthy()
    expect(screen.getByText('展示')).toBeTruthy()
    expect(screen.getByText('🔍 查询')).toBeTruthy()
    // Date input
    expect(document.querySelector('input[type="date"]')).toBeTruthy()
    // Select
    expect(document.querySelector('select')).toBeTruthy()
  })

  it('加载时板块分布不显示', () => {
    renderPage()
    expect(screen.queryByText('📊 板块分布')).toBeNull()
  })

  it('加载时摘要和股票列表不显示', () => {
    renderPage()
    expect(document.querySelector('.summary')).toBeFalsy()
    expect(document.querySelector('.stock-grid')).toBeFalsy()
  })

  it('页面容器使用 page-container', () => {
    renderPage()
    expect(document.querySelector('.page-container')).toBeTruthy()
  })
})
