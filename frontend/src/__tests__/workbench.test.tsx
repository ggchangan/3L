/// <reference types="vitest" />
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Workbench from '../pages/Workbench'

function renderWB() {
  return render(<MemoryRouter><Workbench /></MemoryRouter>)
}

describe('Workbench', () => {
  it('渲染标题', () => {
    renderWB()
    expect(screen.getByText('🧑 交易工作台')).toBeTruthy()
  })

  it('渲染所有区块标题', () => {
    renderWB()
    expect(screen.getByText('今日复盘摘要')).toBeTruthy()
    expect(screen.getByText('📋 明日计划')).toBeTruthy()
    expect(screen.getByText('✍️ 今日操作')).toBeTruthy()
    expect(screen.getByText('🔄 执行复盘')).toBeTruthy()
    expect(screen.getByText('💡 今日反思')).toBeTruthy()
  })

  it('渲染日期导航', () => {
    renderWB()
    expect(screen.getByText('← 前一天')).toBeTruthy()
    expect(screen.getByText('后一天 →')).toBeTruthy()
    expect(screen.getByText('💾 保存交易日志')).toBeTruthy()
  })
})
