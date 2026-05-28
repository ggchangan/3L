/// <reference types="vitest" />
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Watchlist from '../pages/Watchlist'

function renderWL() {
  return render(<MemoryRouter><Watchlist /></MemoryRouter>)
}

describe('Watchlist', () => {
  it('渲染标题', () => {
    renderWL()
    expect(screen.getByText('📋 自选股管理')).toBeTruthy()
  })

  it('渲染方向管理入口', () => {
    renderWL()
    expect(screen.getByText('🎯 方向管理 ▸')).toBeTruthy()
  })

  it('渲染搜索添加区域', () => {
    renderWL()
    expect(screen.getByPlaceholderText('输入代码/名称/首字母搜索...')).toBeTruthy()
  })

  it('渲染筛选框', () => {
    renderWL()
    expect(screen.getByPlaceholderText('🔍 筛选...')).toBeTruthy()
  })
})
