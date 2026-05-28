import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Simulation from '../pages/Simulation'

function renderPage() {
  return render(<MemoryRouter><Simulation /></MemoryRouter>)
}

describe('SimulationPage', () => {
  it('渲染标题', () => {
    renderPage()
    const els = screen.getAllByText('📊 3L 模拟交易 · v33')
    expect(els.length).toBeGreaterThanOrEqual(1)
  })

  it('渲染副标题', () => {
    renderPage()
    expect(screen.getByText('动量主线 · 最强逻辑 · 量价择时 · 细分赛道聚类')).toBeTruthy()
  })

  it('渲染4个概要卡片', () => {
    renderPage()
    expect(screen.getByText('模拟周数')).toBeTruthy()
    expect(screen.getByText('4周累计收益')).toBeTruthy()
    expect(screen.getByText('总交易笔数')).toBeTruthy()
    expect(screen.getByText('引擎版本')).toBeTruthy()
  })

  it('渲染4周标题', () => {
    renderPage()
    expect(screen.getByText('第1周 (4/7~4/10)')).toBeTruthy()
    expect(screen.getByText('第2周 (4/13~4/17)')).toBeTruthy()
    expect(screen.getByText('第3周 (4/20~4/24)')).toBeTruthy()
    expect(screen.getByText('第4周 (4/27~4/30)')).toBeTruthy()
  })

  it('每个周有表格', () => {
    renderPage()
    const tables = document.querySelectorAll('.week-card table')
    expect(tables.length).toBe(4)
  })

  it('渲染周报告链接', () => {
    renderPage()
    const links = screen.getAllByText('📄 周报告')
    expect(links.length).toBe(4)
  })

  it('渲染总体报告链接', () => {
    renderPage()
    expect(screen.getByText('📄 总体')).toBeTruthy()
  })

  it('页面容器使用 page-container', () => {
    renderPage()
    expect(document.querySelector('.page-container')).toBeTruthy()
  })
})
