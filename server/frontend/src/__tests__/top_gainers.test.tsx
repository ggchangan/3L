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
    const els = screen.getAllByText('📈 区间涨幅榜')
    expect(els.length).toBeGreaterThanOrEqual(1)
  })

  it('渲染副标题', () => {
    renderPage()
    expect(screen.getByText('全市场个股 · 指定区间涨幅排序 · 板块分布 · 操作信号')).toBeTruthy()
  })

  it('渲染控制栏（起始+截止日期）', () => {
    renderPage()
    expect(screen.getByText('📅 起始')).toBeTruthy()
    expect(screen.getByText('→ 截止')).toBeTruthy()
    expect(screen.getByText('展示')).toBeTruthy()
    expect(screen.getByText('🔍 查询')).toBeTruthy()
    expect(document.querySelectorAll('input[type="date"]').length).toBe(2)
    expect(document.querySelector('select')).toBeTruthy()
  })

  it('加载时板块分布和股票列表不显示', () => {
    renderPage()
    expect(screen.queryByText('📊 板块分布')).toBeNull()
    expect(document.querySelector('.summary')).toBeFalsy()
    expect(document.querySelector('.stock-grid')).toBeFalsy()
  })

  it('页面容器使用 page-container', () => {
    renderPage()
    expect(document.querySelector('.page-container')).toBeTruthy()
  })
})
