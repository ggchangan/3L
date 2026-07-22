/// <reference types="vitest" />
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../lib/api', () => ({
  fetchReviewToday: vi.fn(),
  fetchReviewStatus: vi.fn(),
  refreshReview: vi.fn(),
}))
vi.mock('../components/MarketCycle', () => ({ default: () => <div>大盘周期已加载</div> }))

import Review from '../pages/Review'
import { fetchReviewToday } from '../lib/api'

describe('Review page contract integration', () => {
  beforeEach(() => vi.clearAllMocks())

  it('从 v3 契约展示当日预估覆盖率和交易门禁', async () => {
    vi.mocked(fetchReviewToday).mockResolvedValue({
      date: '2026-07-22',
      data_status: {
        overall: 'ready',
        stocks: { status: 'confirmed', date: '20260722' },
        index: { status: 'confirmed', date: '20260722' },
        industry: { status: 'estimated', date: '20260722', coverage: 0.9781, coverage_detail: { covered: 312, expected: 319 } },
        concept: { status: 'estimated', date: '20260722', coverage: 0.8533, coverage_detail: { covered: 157, expected: 184 } },
      },
      mainline: { ranking_status: 'estimated', lines: [], secondary: [] },
      buy_signals_review: [],
      trading_plan: {
        buy_priority: [
          { code: '1', name: '可执行股', decision_status: 'executable' },
          { code: '2', name: '候选股', decision_status: 'candidate' },
          { code: '3', name: '阻断股', decision_status: 'blocked' },
        ],
      },
      refresh_status: { status: 'idle' },
    })

    render(<MemoryRouter><Review /></MemoryRouter>)

    expect(await screen.findByText('行业 07-22 · 当日预估 97.8%，312/319')).toBeTruthy()
    expect(screen.getByText('概念 07-22 · 当日预估 85.3%，157/184')).toBeTruthy()
    expect(screen.getByText('✅ 可执行买点 (1)')).toBeTruthy()
    expect(screen.getByText('👀 候选观察 (1)')).toBeTruthy()
    expect(screen.getByText('⛔ 数据阻断 (1)')).toBeTruthy()
  })
})
