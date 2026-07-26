/// <reference types="vitest" />
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

vi.mock('../lib/api', () => ({
  fetchReviewToday: vi.fn(),
  fetchReviewDates: vi.fn(),
  fetchReviewByDate: vi.fn(),
  fetchReviewStatus: vi.fn(),
  refreshReview: vi.fn(),
}))
vi.mock('../components/MarketCycle', () => ({ default: () => <div>大盘周期已加载</div> }))

import Review from '../pages/Review'
import { fetchReviewByDate, fetchReviewDates, fetchReviewToday } from '../lib/api'

describe('Review page contract integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(fetchReviewDates).mockResolvedValue({ dates: ['2026-07-21'] })
    vi.mocked(fetchReviewByDate).mockResolvedValue({ mainline: { all_ranked: [] } })
  })

  it('从 v3 契约展示复盘交易日、预估覆盖率和操作', async () => {
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
          { code: '1', name: '买入股', attention_tier: 'focus', decision_status: 'executable', action_type: '观察' },
          { code: '2', name: '普通买点股', attention_tier: 'watch', decision_status: 'candidate', action_type: '买入' },
          { code: '3', name: '待确认股', attention_tier: 'ordinary', decision_status: 'blocked', action_type: '待确认' },
        ],
        buy_summary: {
          total: 3, focus: 1, watch: 1, ordinary: 1,
          conclusion: '优先跟踪 1 个主线/强动量买点。',
          ranking_rule: '市场过滤 → 主线/强动量 → 个股买点质量 → 板块环境 → 止损风险',
        },
      },
      refresh_status: { status: 'idle' },
    })

    render(<MemoryRouter><Review /></MemoryRouter>)

    expect(await screen.findByText('行业 07-22 · 当日预估 97.8%，312/319')).toBeTruthy()
    expect(screen.getByText('概念 07-22 · 当日预估 85.3%，157/184')).toBeTruthy()
    expect(screen.getByText('复盘交易日 2026-07-22 星期三')).toBeTruthy()
    expect(screen.getByText('① 大盘强弱 · ② 主线动量 · ③ 板块环境 · ④ 个股买点')).toBeTruthy()
    expect(screen.getByText('主线动量与板块环境')).toBeTruthy()
    expect(screen.getByText('🎯 今日买点重点')).toBeTruthy()
    expect(screen.getByText('🔥 重点关注 (1)')).toBeTruthy()
    expect(screen.getByText('👀 次级观察 (1)')).toBeTruthy()
    expect(screen.getAllByText('买入')).toHaveLength(1)
    expect(screen.getByText('观察')).toBeTruthy()
    expect(screen.queryByText('待确认')).toBeNull()
  })
})
