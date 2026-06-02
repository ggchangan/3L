import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Macro from '../pages/Macro'

function renderPage() {
  return render(<MemoryRouter><Macro /></MemoryRouter>)
}

describe('MacroPage', () => {
  it('渲染标题', () => {
    renderPage()
    const els = screen.getAllByText('🌍 宏观环境监控')
    expect(els.length).toBeGreaterThanOrEqual(1)
  })

  it('渲染副标题', () => {
    renderPage()
    expect(screen.getByText('A股大盘 · 全球指数 · 宏观数据 · 汇率 · 外围映射')).toBeTruthy()
  })

  it('渲染加载状态', () => {
    renderPage()
    expect(screen.getByText('正在获取宏观数据...')).toBeTruthy()
    expect(document.querySelector('.spinner')).toBeTruthy()
  })

  it('加载时未渲染数据区块', () => {
    renderPage()
    expect(document.querySelector('.section')).toBeFalsy()
  })

  it('加载时未渲染数据来源标注', () => {
    renderPage()
    // 加载时不显示底部数据来源（只在数据渲染后显示）
    expect(screen.queryByText(/数据来源/)).toBeNull()
  })

  it('页面容器使用 page-container', () => {
    renderPage()
    expect(document.querySelector('.page-container')).toBeTruthy()
  })
})
