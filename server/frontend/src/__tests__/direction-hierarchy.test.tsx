/// <reference types="vitest" />
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Watchlist from '../pages/Watchlist'
import mockData from '../mock/direction-hierarchy.json'

// Mock matchMedia for NavBar
window.matchMedia = vi.fn().mockImplementation((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener: vi.fn(),
  removeListener: vi.fn(),
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  dispatchEvent: vi.fn(),
}))

// Mock fetch globally
const mockFetch = vi.fn()
global.fetch = mockFetch as any

function renderWL() {
  return render(<MemoryRouter><Watchlist /></MemoryRouter>)
}

describe('Watchlist — 方向分层管理', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Default mock: 方向数据
    mockFetch.mockImplementation((url: string) => {
      if (url === '/api/directions/get') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockData),
        })
      }
      if (url === '/api/watchlist/analysis') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ stocks: [] }),
        })
      }
      if (url === '/api/trend-tracked') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ candidates: [] }),
        })
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    })
  })

  it('渲染标题', () => {
    renderWL()
    expect(screen.getByText('📋 自选股管理')).toBeTruthy()
  })

  it('渲染方向管理入口', async () => {
    renderWL()
    await waitFor(() => {
      expect(screen.getByText(/🎯 方向管理/)).toBeTruthy()
    })
  })

  it('点击方向管理后展示大类分组', async () => {
    renderWL()
    await waitFor(() => {
      const btn = screen.getByText(/🎯 方向管理/)
      btn.click()
    })
    // 大类应该显示
    await waitFor(() => {
      expect(screen.getByText(/📁 科技/)).toBeTruthy()
      expect(screen.getByText(/📁 医药/)).toBeTruthy()
      expect(screen.getByText(/📁 新能源/)).toBeTruthy()
    })
    // 细分方向数量
    await waitFor(() => {
      expect(screen.getByText(/5个细分/)).toBeTruthy()
    })
  })

  it('新增大类接口调用', async () => {
    mockFetch.mockImplementation((url: string, opts?: any) => {
      if (url === '/api/directions/get') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(mockData),
        })
      }
      if (url === '/api/directions/category/add' && opts?.method === 'POST') {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({ success: true }),
        })
      }
      if (url === '/api/watchlist/analysis') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ stocks: [] }) })
      }
      if (url === '/api/trend-tracked') {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ candidates: [] }) })
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) })
    })

    renderWL()
    await waitFor(() => {
      const btn = screen.getByText(/🎯 方向管理/)
      btn.click()
    })
    // TODO: 检查添加大类输入框存在
    // 这部分需要等前端实现了才知道具体渲染什么
  })
})
