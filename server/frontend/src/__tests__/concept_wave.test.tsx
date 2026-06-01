import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

// Mock fetch globally
const mockData = {
  success: true,
  date: '2026-05-31',
  stats: { total: 5, valley: 1, peak: 0, rise: 0, decline: 3, mid: 1, alerts_count: 1, new_this_week: 0 },
  grouped: {
    valley: [{
      code: 'BK1682', name: 'AI算力', stage: '波谷', vl_score: 4, pk_score: 0,
      bias20: -6.3, bias5: -1.2, change_5d: -1.2, change_1d: -0.5,
      volume_ratio: 0.52, volume_signal: 'shrink', ema10_slope: -0.12, two_sigma: -1.8,
      mainline_rank: 3, mainline_badge: 'gold',
      entry_window: true, vs_market_5d: 3.2, vs_market_20d: -2.1,
      historical_gain: 18.5, last_peak_date: '2026-05-15', last_trough_date: '2026-05-28',
      cycle_days: 23, cycle_count: 2,
      related_stocks: ['中际旭创', '寒武纪', '光迅科技'],
      related_count: 3, related_codes: ['300308', '688256', '002281'],
      stock_count: 35,
      wave_data: [],
      annotations: [],
      klines: [],
      chart_annotations: [],
      reasoning_chain: {
        market: {
          position: '波中偏谷', position_pct: '5-7成',
          volume_level: '中等', volume_amount: '1.2万亿',
          top_mainlines: [
            { name: '半导体', rank: 1, days: 5 },
            { name: '电子化学品', rank: 2, days: 3 },
            { name: '元件', rank: 3, days: 8 },
          ]
        },
        concept_analysis: {
          reason: 'BIAS20深度负值+极度缩量+EMA10走平 → 波谷确认'
        },
        stock_signals: [
          { code: '300308', name: '中际旭创', signal: 'buy', buy_type: '中继买点', reason: '缩量回踩EMA5成功' },
          { code: '002281', name: '光迅科技', signal: 'hold', buy_type: '', reason: '' },
        ]
      }
    }],
    peak: [],
    rise: [],
    decline: [],
    mid: [],
  },
  alerts: [{ code: 'BK1682', name: 'AI算力', vl_score: 4, reason: 'BIAS20=-6.3%', date: '2026-05-31' }],
  new_hot: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  globalThis.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(mockData),
    })
  ) as any
})

describe('ConceptWaveTracking', () => {
  it('渲染标题', async () => {
    const ConceptWaveTracking = (await import('../pages/ConceptWaveTracking')).default
    render(<MemoryRouter><ConceptWaveTracking /></MemoryRouter>)
    expect(screen.getByText(/概念板块波谷追踪/)).toBeTruthy()
  })

  it('加载完成后显示统计卡', async () => {
    const ConceptWaveTracking = (await import('../pages/ConceptWaveTracking')).default
    render(<MemoryRouter><ConceptWaveTracking /></MemoryRouter>)

    await waitFor(() => {
      expect(screen.getByText('当前波谷信号')).toBeTruthy()
    })
    expect(screen.getByText('强信号告警')).toBeTruthy()
    expect(screen.getByText('追踪概念总数')).toBeTruthy()
  })

  it('加载完成后显示波谷组第一张卡片', async () => {
    const ConceptWaveTracking = (await import('../pages/ConceptWaveTracking')).default
    render(<MemoryRouter><ConceptWaveTracking /></MemoryRouter>)

    await waitFor(() => {
      // AI算力出现在卡片名和告警区，用 getAllByText
      const items = screen.getAllByText('AI算力')
      expect(items.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('显示告警区块', async () => {
    const ConceptWaveTracking = (await import('../pages/ConceptWaveTracking')).default
    render(<MemoryRouter><ConceptWaveTracking /></MemoryRouter>)

    await waitFor(() => {
      // 告警文字的 React 渲染包含空格
      const items = screen.getAllByText(/BIAS20/)
      expect(items.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('加载中显示占位文本', async () => {
    // 不resolve fetch，模拟加载中
    globalThis.fetch = vi.fn(() => new Promise(() => {})) as any
    const ConceptWaveTracking = (await import('../pages/ConceptWaveTracking')).default
    render(<MemoryRouter><ConceptWaveTracking /></MemoryRouter>)
    expect(screen.getByText('正在加载概念板块数据…')).toBeTruthy()
  })

  it('fetch失败显示错误提示', async () => {
    globalThis.fetch = vi.fn(() => Promise.reject(new Error('网络错误'))) as any
    const ConceptWaveTracking = (await import('../pages/ConceptWaveTracking')).default
    render(<MemoryRouter><ConceptWaveTracking /></MemoryRouter>)

    await waitFor(() => {
      expect(screen.getByText(/⚠️/)).toBeTruthy()
    })
  })

  it('展开卡片后显示推理链', async () => {
    const ConceptWaveTracking = (await import('../pages/ConceptWaveTracking')).default
    render(<MemoryRouter><ConceptWaveTracking /></MemoryRouter>)

    await waitFor(() => {
      const aiItems = screen.getAllByText('AI算力')
      expect(aiItems.length).toBeGreaterThanOrEqual(1)
    })

    // 点击卡片名称展开
    const aiItems = screen.getAllByText('AI算力')
    const firstAi = aiItems[0]
    // 点击包含这个名称的卡片主体区域
    const cardMain = firstAi.closest('.cw-main') as HTMLElement
    if (cardMain) {
      cardMain.click()
    } else {
      // fallback: 点击名称本身
      firstAi.click()
    }

    await waitFor(() => {
      // 推理链显示大盘信息
      expect(screen.getByText(/波中偏谷/)).toBeTruthy()
    })
    expect(screen.getByText(/5-7成/)).toBeTruthy()
    expect(screen.getByText(/半导体/)).toBeTruthy()
    // 概念分析
    expect(screen.getByText(/波谷确认/)).toBeTruthy()
    // 个股信号
    const xcItems = screen.getAllByText(/中际旭创/)
    expect(xcItems.length).toBeGreaterThanOrEqual(1)
  })
})
