import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Skills from '../pages/Skills'

function renderPage() {
  return render(<MemoryRouter><Skills /></MemoryRouter>)
}

describe('SkillsPage', () => {
  it('渲染标题', () => {
    renderPage()
    const els = screen.getAllByText('📖 Skills 追踪')
    expect(els.length).toBeGreaterThanOrEqual(1)
  })

  it('渲染副标题', () => {
    renderPage()
    expect(screen.getByText('所有Skills一览 + 逐日更新记录')).toBeTruthy()
  })

  it('渲染全部Skills区块标题', () => {
    renderPage()
    expect(screen.getByText('📦 全部Skills')).toBeTruthy()
  })

  it('渲染更新记录区块标题', () => {
    renderPage()
    expect(screen.getByText('📝 更新记录')).toBeTruthy()
  })

  it('至少包含一个skill名称', () => {
    renderPage()
    expect(screen.getAllByText('daily-achievements-page').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('daily-3l-monitor').length).toBeGreaterThanOrEqual(1)
  })

  it('渲染日期徽章', () => {
    renderPage()
    expect(screen.getByText('2026-05-22')).toBeTruthy()
    expect(screen.getByText('2026-05-20')).toBeTruthy()
    expect(screen.getByText('2026-05-19')).toBeTruthy()
  })

  it('渲染footer', () => {
    renderPage()
    expect(screen.getByText('3L 交易体系 · Hermes Agent · 2026')).toBeTruthy()
  })

  it('页面容器使用 page-container', () => {
    renderPage()
    expect(document.querySelector('.page-container')).toBeTruthy()
  })
})
