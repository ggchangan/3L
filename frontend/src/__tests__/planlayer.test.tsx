import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import PlanLayer from '../components/PlanLayer'

// 模拟 API 模块
vi.mock('../lib/api', () => ({
  getYesterdayStr: () => '2026-05-27',
  fetchWorkbenchPlan: vi.fn(),
  fetchActiveAlarms: vi.fn(),
  fetchReviewToday: vi.fn(),
}))

import {
  fetchWorkbenchPlan,
  fetchActiveAlarms,
  fetchReviewToday,
} from '../lib/api'
import type { PlanItem, StoredAlarm } from '../lib/api'

/** 带止损的持仓数据（真实API字段名） */
const mockHoldings = [
  {
    code: '301232',
    name: '飞沃科技',
    stop_loss_price: 128.88,
    stop_loss_pct: -7.66,
    price: 139.50,
    change: -1.2,
    signal: 'hold' as const,
    stage: '震荡',
    structure: '区间震荡',
  },
  {
    code: '002371',
    name: '北方华创',
    stop_loss_price: 614.63,
    stop_loss_pct: -6.13,
    price: 655.00,
    change: 0.8,
    signal: 'hold' as const,
    stage: '上涨',
    structure: '趋势',
  },
]

/** 不带止损价的持仓（没有 stop_loss_price） */
const mockHoldingsNoStopLoss = [
  {
    code: '000988',
    name: '华工科技',
    // 没有 stop_loss_price
    price: 168.00,
    change: 0.5,
    signal: 'hold' as const,
    stage: '震荡',
    structure: '震荡',
  },
]

function mockPlan(): PlanItem[] {
  return [
    { stock: '飞沃科技(301232)', condition: '区间底部', alert: { type: 'price', enabled: true, condition: '' }, stop_loss: 128.88, stop_loss_pct: -7.66 },
    { stock: '北方华创(002371)', condition: '中继买点', alert: { type: 'deviation', enabled: true, condition: '6' }, stop_loss: 614.63, stop_loss_pct: -6.13 },
  ]
}

function mockAlarms(): StoredAlarm[] {
  return [
    { id: 'a1', stock: '飞沃科技(301232)', stock_code: '301232', type: 'price', enabled: true, stop_loss: 128.88, stop_loss_pct: -7.66, condition: '', created: '2026-05-28', status: 'active', expires_days: 7 },
    { id: 'a2', stock: '北方华创(002371)', stock_code: '002371', type: 'deviation', enabled: true, stop_loss: 614.63, stop_loss_pct: -6.13, condition: '6', created: '2026-05-28', status: 'active', expires_days: 7 },
    { id: 'a3', stock: '华工科技(000988)', stock_code: '000988', type: 'price', enabled: true, stop_loss: 163.88, stop_loss_pct: -2.50, condition: '', created: '2026-05-28', status: 'active', expires_days: 7 },
  ]
}

beforeEach(() => {
  vi.clearAllMocks()
  const yPlan = { plan: { buy: [], sell: [], watch: [] } }
  const tPlan = { plan: { buy: mockPlan(), sell: [], watch: [] } }
  vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(yPlan as any)  // yesterday
  vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(tPlan as any)  // today
})

// ── 持仓止损 + 计划报警 ──

describe('PlanLayer — 持仓止损', () => {

  beforeEach(() => {
    vi.mocked(fetchActiveAlarms).mockResolvedValue({ alarms: mockAlarms(), count: 3 } as any)
  })

  it('渲染持仓止损区块（持仓有止损数据时）', async () => {
    vi.mocked(fetchReviewToday).mockResolvedValue({ holdings: mockHoldings } as any)

    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText('🔴 持仓止损')).toBeTruthy()
    })

    const fyItems = screen.getAllByText(/飞沃科技/)
    expect(fyItems.length).toBeGreaterThanOrEqual(1)
    const bfItems = screen.getAllByText(/北方华创/)
    expect(bfItems.length).toBeGreaterThanOrEqual(1)
    const sl128 = screen.getAllByText(/128\.88/)
    expect(sl128.length).toBeGreaterThanOrEqual(1)
    const sl614 = screen.getAllByText(/614\.63/)
    expect(sl614.length).toBeGreaterThanOrEqual(1)
    const pct766 = screen.getAllByText(/-7\.66%/)
    expect(pct766.length).toBeGreaterThanOrEqual(1)
    const pct613 = screen.getAllByText(/-6\.13%/)
    expect(pct613.length).toBeGreaterThanOrEqual(1)
  })

  it('持仓止损区块=持仓中有止损价才显示', async () => {
    vi.mocked(fetchReviewToday).mockResolvedValue({ holdings: mockHoldingsNoStopLoss } as any)

    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText('📋 今日计划')).toBeTruthy()
    })

    expect(screen.queryByText('🔴 持仓止损')).toBeNull()
  })

  it('计划报警区块=过滤掉持仓股的价格报警', async () => {
    vi.mocked(fetchReviewToday).mockResolvedValue({ holdings: mockHoldings } as any)

    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText('🔴 持仓止损')).toBeTruthy()
    })
    await waitFor(() => {
      expect(screen.getByText('🟡 计划报警')).toBeTruthy()
    })

    // 华工科技的报警（非持仓的price报警）应该显示
    expect(screen.getByText(/华工科技/)).toBeTruthy()
    // 北方华创的偏差报警保留（显示 ±6%）
    expect(screen.getByText(/±6%/)).toBeTruthy()
  })

  it('没有报警时计划报警区块不显示', async () => {
    vi.mocked(fetchReviewToday).mockResolvedValue({ holdings: mockHoldings } as any)
    vi.mocked(fetchActiveAlarms).mockResolvedValue({ alarms: [], count: 0 } as any)

    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText('📋 今日计划')).toBeTruthy()
    })

    expect(screen.queryByText('🟡 计划报警')).toBeNull()
  })

})

// ── 可折叠 ──

describe('PlanLayer — 可折叠', () => {

  beforeEach(() => {
    vi.mocked(fetchActiveAlarms).mockResolvedValue({ alarms: mockAlarms(), count: 3 } as any)
    vi.mocked(fetchReviewToday).mockResolvedValue({ holdings: mockHoldings } as any)
  })

  it('默认展开（内容可见）', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText('📋 今日计划')).toBeTruthy()
    })

    const fyItems = screen.getAllByText(/飞沃科技/)
    expect(fyItems.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('🔴 持仓止损')).toBeTruthy()
    expect(screen.getByText('🟡 计划报警')).toBeTruthy()
  })

  it('点击标题折叠内容', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText('📋 今日计划')).toBeTruthy()
    })

    const title = screen.getByText('📋 今日计划')

    // 点击标题折叠
    fireEvent.click(title)
    await waitFor(() => {
      expect(screen.queryByText(/飞沃科技/)).toBeNull()
    })
    expect(screen.queryByText('🔴 持仓止损')).toBeNull()
    expect(screen.queryByText('🟡 计划报警')).toBeNull()

    // 再次点击展开
    fireEvent.click(title)
    await waitFor(() => {
      const items = screen.getAllByText(/飞沃科技/)
      expect(items.length).toBeGreaterThanOrEqual(1)
    })
    expect(screen.getByText('🔴 持仓止损')).toBeTruthy()
  })

})
