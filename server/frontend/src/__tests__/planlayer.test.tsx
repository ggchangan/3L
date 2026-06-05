import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import PlanLayer from '../components/PlanLayer'

// 模拟 API 模块
vi.mock('../lib/api', () => ({
  getYesterdayStr: () => '2026-06-04',
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

/** 带止损的持仓数据 */
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

/** 无止损的持仓 */
const mockHoldingsNoStopLoss = [
  {
    code: '000988',
    name: '华工科技',
    price: 168.00,
    change: 0.5,
    signal: 'hold' as const,
    stage: '震荡',
    structure: '震荡',
  },
]

/** 今日计划：买入（含持仓股+候选股） */
function mockPlanBuy(): PlanItem[] {
  return [
    // 持仓股（与 holdings 重复）
    { stock: '飞沃科技(301232)', condition: '区间底部', alert: { type: 'price', enabled: true, condition: '' }, stop_loss: 128.88, stop_loss_pct: -7.66 },
    // 非持仓候选股
    { stock: '德龙激光(688170)', condition: '等待信号确认' },
  ]
}

/** 今日计划：观察 */
function mockPlanWatch(): PlanItem[] {
  return [
    // 非持仓
    { stock: '中际旭创(300308)', condition: '趋势延续', stop_loss: 68.50, stop_loss_pct: -5.0 },
  ]
}

/** 今日计划：卖出 */
function mockPlanSell(): PlanItem[] {
  return [
    // 持仓股（与 holdings 重复）
    { stock: '北方华创(002371)', condition: '中继买点', alert: { type: 'deviation', enabled: true, condition: '6' }, stop_loss: 614.63, stop_loss_pct: -6.13 },
  ]
}

function mockAlarms(): StoredAlarm[] {
  return [
    { id: 'a1', stock: '飞沃科技(301232)', stock_code: '301232', type: 'price', enabled: true, stop_loss: 128.88, stop_loss_pct: -7.66, condition: '', created: '2026-06-04', status: 'active', expires_days: 7 },
    { id: 'a2', stock: '北方华创(002371)', stock_code: '002371', type: 'deviation', enabled: true, stop_loss: 614.63, stop_loss_pct: -6.13, condition: '6', created: '2026-06-04', status: 'active', expires_days: 7 },
    { id: 'a3', stock: '中际旭创(300308)', stock_code: '300308', type: 'price', enabled: true, stop_loss: 68.50, stop_loss_pct: -5.0, condition: '', created: '2026-06-04', status: 'active', expires_days: 7 },
  ]
}

beforeEach(() => {
  vi.clearAllMocks()
})

// ── 持仓操作（持仓股合并计划信息） ──

describe('PlanLayer — 持仓操作', () => {

  beforeEach(() => {
    const yPlan = { plan: { buy: [], sell: [], watch: [] } }
    const tPlan = { plan: { buy: mockPlanBuy(), sell: mockPlanSell(), watch: mockPlanWatch() } }
    vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(yPlan as any)
    vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(tPlan as any)
    vi.mocked(fetchActiveAlarms).mockResolvedValue({ alarms: mockAlarms(), count: 3 } as any)
    vi.mocked(fetchReviewToday).mockResolvedValue({ holdings: mockHoldings } as any)
  })

  it('持仓操作区块显示持仓股', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText('🔴 持仓操作')).toBeTruthy()
    })

    // 北方华创同时出现在持仓操作和报警区，用 getAllByText 检查至少出现
    expect(screen.getAllByText(/飞沃科技/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/北方华创/).length).toBeGreaterThanOrEqual(1)
  })

  it('持仓操作显示止损价', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      // 128.88 同时出现在持仓操作和报警区 → getAllByText
      const items = screen.getAllByText(/128\.88/)
      expect(items.length).toBeGreaterThanOrEqual(1)
    })
    // 614.63 同理
    const items614 = screen.getAllByText(/614\.63/)
    expect(items614.length).toBeGreaterThanOrEqual(1)
    const items766 = screen.getAllByText(/-7\.66%/)
    expect(items766.length).toBeGreaterThanOrEqual(1)
    const items613 = screen.getAllByText(/-6\.13%/)
    expect(items613.length).toBeGreaterThanOrEqual(1)
  })

  it('持仓操作合并该股的计划方向（买入/卖出）', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getAllByText(/飞沃科技/).length).toBeGreaterThanOrEqual(1)
    })

    expect(screen.getByText(/→ 买入/)).toBeTruthy()
    expect(screen.getByText(/→ 卖出/)).toBeTruthy()
  })

  it('持仓操作显示计划条件', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText(/区间底部/)).toBeTruthy()
    })
    expect(screen.getByText(/中继买点/)).toBeTruthy()
  })

  it('持仓操作显示实时价格和涨跌幅', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      // "现价" 在两只持仓股各出现一次 → getAllByText
      const items = screen.getAllByText(/现价/)
      expect(items.length).toBeGreaterThanOrEqual(1)
    })
    const p139 = screen.getAllByText(/139\.5/)
    expect(p139.length).toBeGreaterThanOrEqual(1)
    const m12 = screen.getAllByText(/-1\.2%/)
    expect(m12.length).toBeGreaterThanOrEqual(1)
  })

  it('持仓操作计数正确', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      // "2只" 在持仓操作和候选区各出现一次 → getAllByText
      const badges = screen.getAllByText(/2只/)
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
  })
})

// ── 候选（非持仓的计划项） ──

describe('PlanLayer — 候选', () => {

  beforeEach(() => {
    const yPlan = { plan: { buy: [], sell: [], watch: [] } }
    const tPlan = { plan: { buy: mockPlanBuy(), sell: mockPlanSell(), watch: mockPlanWatch() } }
    vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(yPlan as any)
    vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(tPlan as any)
    vi.mocked(fetchActiveAlarms).mockResolvedValue({ alarms: mockAlarms(), count: 3 } as any)
    vi.mocked(fetchReviewToday).mockResolvedValue({ holdings: mockHoldings } as any)
  })

  it('候选区块显示非持仓的计划项', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText('🟢 候选')).toBeTruthy()
    })

    expect(screen.getByText(/德龙激光/)).toBeTruthy()
    const items = screen.getAllByText(/中际旭创/)
    expect(items.length).toBeGreaterThanOrEqual(1)
  })

  it('候选计数正确（2只非持仓）', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      const badges = screen.getAllByText(/2只/)
      expect(badges.length).toBeGreaterThanOrEqual(1)
    })
  })

  it('候选显示条件和止损', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText(/等待信号确认/)).toBeTruthy()
    })
    expect(screen.getByText(/趋势延续/)).toBeTruthy()
    // "68.5" 同时出现在候选止损区和报警区 → getAllByText
    const items = screen.getAllByText(/68\.5/)
    expect(items.length).toBeGreaterThanOrEqual(1)
  })
})

// ── 无持仓时 ──

describe('PlanLayer — 无持仓', () => {

  beforeEach(() => {
    const yPlan = { plan: { buy: [], sell: [], watch: [] } }
    const tPlan = { plan: { buy: mockPlanBuy(), sell: mockPlanSell(), watch: mockPlanWatch() } }
    vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(yPlan as any)
    vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(tPlan as any)
    vi.mocked(fetchActiveAlarms).mockResolvedValue({ alarms: mockAlarms(), count: 3 } as any)
    // 空持仓
    vi.mocked(fetchReviewToday).mockResolvedValue({ holdings: [] } as any)
  })

  it('无持仓时持仓操作区块不显示', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.queryByText('🔴 持仓操作')).toBeNull()
    })
  })

  it('无持仓时所有计划项都归入候选', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText('🟢 候选')).toBeTruthy()
    })

    // 飞沃科技也在报警区出现 → getAllByText
    const fyItems = screen.getAllByText(/飞沃科技/)
    expect(fyItems.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/德龙激光/)).toBeTruthy()
  })
})

// ── 无计划项时 ──

describe('PlanLayer — 无计划', () => {

  beforeEach(() => {
    const yPlan = { plan: { buy: [], sell: [], watch: [] } }
    const tPlan = { plan: { buy: [], sell: [], watch: [] } }
    vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(yPlan as any)
    vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(tPlan as any)
    vi.mocked(fetchActiveAlarms).mockResolvedValue({ alarms: [], count: 0 } as any)
    vi.mocked(fetchReviewToday).mockResolvedValue({ holdings: mockHoldings } as any)
  })

  it('无计划但有持仓时，只显示持仓操作区块', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText('🔴 持仓操作')).toBeTruthy()
    })
    expect(screen.queryByText('🟢 候选')).toBeNull()
  })

  it('持仓操作显示无方向提示（纯持仓）', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText(/飞沃科技/)).toBeTruthy()
    })
    expect(screen.queryByText(/→ 买入/)).toBeNull()
    expect(screen.queryByText(/→ 卖出/)).toBeNull()
  })
})

// ── 计划报警（保持现有逻辑） ──

describe('PlanLayer — 计划报警', () => {

  beforeEach(() => {
    const yPlan = { plan: { buy: [], sell: [], watch: [] } }
    const tPlan = { plan: { buy: mockPlanBuy(), sell: mockPlanSell(), watch: mockPlanWatch() } }
    vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(yPlan as any)
    vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(tPlan as any)
    vi.mocked(fetchReviewToday).mockResolvedValue({ holdings: mockHoldings } as any)
  })

  it('保留报警区块', async () => {
    vi.mocked(fetchActiveAlarms).mockResolvedValue({ alarms: mockAlarms(), count: 3 } as any)
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText('🟡 计划报警')).toBeTruthy()
    })
  })

  it('无报警时报警区块不显示', async () => {
    vi.mocked(fetchActiveAlarms).mockResolvedValue({ alarms: [], count: 0 } as any)
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.queryByText('🟡 计划报警')).toBeNull()
    })
  })
})

// ── 可折叠 ──

describe('PlanLayer — 可折叠', () => {

  beforeEach(() => {
    const yPlan = { plan: { buy: [], sell: [], watch: [] } }
    const tPlan = { plan: { buy: mockPlanBuy(), sell: mockPlanSell(), watch: mockPlanWatch() } }
    vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(yPlan as any)
    vi.mocked(fetchWorkbenchPlan).mockResolvedValueOnce(tPlan as any)
    vi.mocked(fetchActiveAlarms).mockResolvedValue({ alarms: mockAlarms(), count: 3 } as any)
    vi.mocked(fetchReviewToday).mockResolvedValue({ holdings: mockHoldings } as any)
  })

  it('默认展开（内容可见）', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText('📋 今日计划')).toBeTruthy()
    })
    expect(screen.getByText('🔴 持仓操作')).toBeTruthy()
    expect(screen.getByText('🟢 候选')).toBeTruthy()
    expect(screen.getByText('🟡 计划报警')).toBeTruthy()
  })

  it('点击标题折叠内容', async () => {
    render(<PlanLayer />)

    await waitFor(() => {
      expect(screen.getByText('📋 今日计划')).toBeTruthy()
    })

    const title = screen.getByText('📋 今日计划')

    // 点击折叠
    fireEvent.click(title)
    await waitFor(() => {
      expect(screen.queryByText('🔴 持仓操作')).toBeNull()
    })
    expect(screen.queryByText('🟢 候选')).toBeNull()
    expect(screen.queryByText('🟡 计划报警')).toBeNull()

    // 再次点击展开
    fireEvent.click(title)
    await waitFor(() => {
      expect(screen.getByText('🔴 持仓操作')).toBeTruthy()
    })
    expect(screen.getByText('🟢 候选')).toBeTruthy()
  })
})
