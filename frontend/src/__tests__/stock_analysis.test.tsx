import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import StockAnalysis from '../pages/StockAnalysis'

function renderPage() {
  return render(<MemoryRouter><StockAnalysis /></MemoryRouter>)
}

describe('StockAnalysisPage', () => {
  it('渲染标题', () => {
    renderPage()
    const els = screen.getAllByText('📊 个股买点检测')
    expect(els.length).toBeGreaterThanOrEqual(1)
  })

  it('渲染副标题', () => {
    renderPage()
    expect(screen.getByText('输入股票代码或名称，查看3L量价分析')).toBeTruthy()
  })

  it('渲染搜索输入框', () => {
    renderPage()
    const input = document.querySelector('input[type="text"]')
    expect(input).toBeTruthy()
    expect(input?.getAttribute('placeholder')).toContain('股票代码')
  })

  it('渲染分析按钮', () => {
    renderPage()
    expect(screen.getByText('分析')).toBeTruthy()
  })

  it('渲染回测按钮', () => {
    renderPage()
    expect(screen.getByText('📊 回测')).toBeTruthy()
  })

  it('初始显示空状态提示', () => {
    renderPage()
    expect(screen.getByText('输入股票代码或名称开始分析')).toBeTruthy()
  })

  it('渲染底部数据来源提示', () => {
    renderPage()
    expect(screen.getByText(/数据来源/)).toBeTruthy()
  })

  it('页面容器使用 page-container', () => {
    renderPage()
    expect(document.querySelector('.page-container')).toBeTruthy()
  })
})
