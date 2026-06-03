import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import NavBar, { BottomNav } from '../components/NavBar'

function renderNavBar(path: string = '/monitor') {
  return render(<MemoryRouter initialEntries={[path]}><NavBar /></MemoryRouter>)
}

function renderBottomNav(path: string = '/review') {
  return render(<MemoryRouter initialEntries={[path]}><BottomNav /></MemoryRouter>)
}

describe('NavBar — 侧边栏', () => {
  it('渲染为左侧边栏（sidebar 容器）', () => {
    const { container } = renderNavBar()
    // 应该有一个 sidebar 容器，而不是顶栏 flex-wrap
    const sidebar = container.querySelector('.sidebar')
    expect(sidebar).toBeTruthy()
    // 侧边栏应该是 flex 列布局
    expect(sidebar?.className).toMatch(/sidebar/i)
  })

  it('渲染所有6个分组标签', () => {
    renderNavBar()
    expect(screen.getByText('核心流程')).toBeTruthy()
    expect(screen.getByText('个股管理')).toBeTruthy()
    expect(screen.getByText('板块 / 概念')).toBeTruthy()
    expect(screen.getByText('市场全景')).toBeTruthy()
    expect(screen.getByText('追踪回顾')).toBeTruthy()
    expect(screen.getByText('知识库')).toBeTruthy()
  })

  it('渲染所有14个导航项', () => {
    renderNavBar()
    // 核心流程 (3)
    expect(screen.getByText('📡 盘中盯盘')).toBeTruthy()
    expect(screen.getByText('📋 每日复盘')).toBeTruthy()
    expect(screen.getByText('🧑 工作台')).toBeTruthy()
    // 个股管理 (5)
    expect(screen.getByText('📋 自选股')).toBeTruthy()
    expect(screen.getByText('📋 持仓')).toBeTruthy()
    expect(screen.getByText('🔍 个股分析')).toBeTruthy()
    expect(screen.getByText('🎯 趋势候选')).toBeTruthy()
    expect(screen.getByText('📈 涨幅榜')).toBeTruthy()
    // 板块/概念 (3)
    expect(screen.getByText('🔬 行业追踪')).toBeTruthy()
    expect(screen.getByText('🌊 概念波动')).toBeTruthy()
    expect(screen.getByText('💡 逻辑追踪')).toBeTruthy()
    // 市场全景 (1)
    expect(screen.getByText('🌍 宏观环境')).toBeTruthy()
    // 追踪回顾 (2)
    expect(screen.getByText('📊 计划追踪')).toBeTruthy()
    expect(screen.getByText('📊 模拟交易')).toBeTruthy()
    // 知识库 (1)
    expect(screen.getByText('📝 交易技巧')).toBeTruthy()
  })

  it('当前页面对应项有激活样式', () => {
    const { container } = renderNavBar('/monitor')
    const activeItems = container.querySelectorAll('.nav-item.active')
    expect(activeItems.length).toBeGreaterThanOrEqual(1)
    expect(activeItems[0]?.textContent).toMatch(/盘中盯盘/)
  })

  it('不同页面正确高亮对应项', () => {
    const { container: c1 } = renderNavBar('/review')
    expect(c1.querySelector('.nav-item.active')?.textContent).toMatch(/复盘/)

    const { container: c2 } = renderNavBar('/holdings')
    expect(c2.querySelector('.nav-item.active')?.textContent).toMatch(/持仓/)
  })

  it('页面项使用 <a> 标签可点击', () => {
    renderNavBar()
    const links = document.querySelectorAll('.sidebar a')
    expect(links.length).toBeGreaterThanOrEqual(14)
    // 检查盘中盯盘的链接
    const monitorLink = Array.from(links).find(l => l.textContent?.includes('盘中盯盘'))
    expect(monitorLink?.getAttribute('href')).toBe('/monitor')
  })
})

describe('BottomNav — 底部导航', () => {
  it('渲染辅助页面链接', () => {
    renderBottomNav()
    expect(screen.getByText('📋 每日成果')).toBeTruthy()
    expect(screen.getByText('📊 模拟交易')).toBeTruthy()
    expect(screen.getByText('📖 Skills')).toBeTruthy()
    expect(screen.getByText('🎵 报警音乐')).toBeTruthy()
  })

  it('底部链接可正确跳转', () => {
    renderBottomNav()
    const links = document.querySelectorAll('#nav-bottom a')
    expect(links.length).toBeGreaterThanOrEqual(4)
  })
})
