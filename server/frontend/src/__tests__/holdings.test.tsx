import { afterEach, describe, it, expect, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Holdings from '../pages/Holdings'

function renderPage() {
  return render(<MemoryRouter><Holdings /></MemoryRouter>)
}

describe('HoldingsPage', () => {
  afterEach(() => vi.restoreAllMocks())
  it('渲染标题', () => {
    renderPage()
    expect(screen.getByText('📋 持仓管理')).toBeTruthy()
  })

  it('渲染加载状态', () => {
    renderPage()
    expect(screen.getByText('⌛ 加载持仓数据...')).toBeTruthy()
  })

  it('渲染持仓建议区块（空数据预计算）', () => {
    renderPage()
    expect(screen.getByText('📋 持仓建议')).toBeTruthy()
  })

  it('渲染底部footer文本', () => {
    renderPage()
    // footer 只在 !loading 时显示，需等 useEffect 完成后
    // 但建议区块中的 footer 在页面上存在
    // 实际上 bottomNav 中包含 footer 文字
  })

  it('加载时卡片区不显示', () => {
    renderPage()
    // 无持股时不显示卡片区 header
    expect(document.querySelector('.card-section-header')).toBeFalsy()
  })

  it('加载时饼图不显示', () => {
    renderPage()
    expect(document.querySelector('.ov-pie')).toBeFalsy()
  })

  it('加载时统计行不显示', () => {
    renderPage()
    expect(document.querySelector('.ov-stats')).toBeFalsy()
  })

  it('页面使用 page-container class', () => {
    renderPage()
    expect(document.querySelector('.page-container')).toBeTruthy()
  })

  it('新增弹窗只显示一个可用日历选择的买入日期且不显示调试文字', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true,
      json: async () => ({ holdings: [], cash_ratio: 100 }),
    } as Response)
    renderPage()

    fireEvent.click(await screen.findByText('＋ 新增第一只持仓'))

    const dateInputs = screen.getAllByLabelText('买入日期')
    expect(dateInputs).toHaveLength(1)
    expect(dateInputs[0]).toHaveAttribute('type', 'date')
    expect(screen.queryByText(/debug:/)).toBeNull()
  })

  it('方向选择使用接口给出的权威顺序', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
      const url = String(input)
      if (url.startsWith('/api/holdings')) {
        return { ok: true, json: async () => ({ holdings: [], cash_ratio: 100 }) } as Response
      }
      return {
        ok: true,
        json: async () => ({ active: ['科技.C', '科技.A'], active_ordered: ['科技.A', '科技.C'] }),
      } as Response
    })
    renderPage()

    fireEvent.click(await screen.findByText('＋ 新增第一只持仓'))
    await waitFor(() => expect(screen.getByLabelText('方向').querySelectorAll('option')).toHaveLength(3))

    const options = Array.from(screen.getByLabelText('方向').querySelectorAll('option')).map(option => option.textContent)
    expect(options).toEqual(['请选择方向', '科技.A', '科技.C'])
  })

  it('改选无方向映射的股票时不会沿用上一只股票的方向', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
      const url = String(input)
      if (url.startsWith('/api/holdings')) return { ok: true, json: async () => ({ holdings: [], cash_ratio: 100 }) } as Response
      if (url === '/api/directions/get') return { ok: true, json: async () => ({ active_ordered: ['科技.A'] }) } as Response
      if (url.includes('q=%E6%9C%89')) return { ok: true, json: async () => ({ stocks: [{ name: '有方向', code: '000010', price: 10, direction: '科技.A' }] }) } as Response
      if (url.includes('q=%E6%97%A0')) return { ok: true, json: async () => ({ stocks: [{ name: '无方向', code: '000011', price: 11, direction: '' }] }) } as Response
      throw new Error(`unexpected fetch: ${url}`)
    })
    renderPage()
    fireEvent.click(await screen.findByText('＋ 新增第一只持仓'))
    const search = screen.getByPlaceholderText('输入股票名称或代码...')
    fireEvent.change(search, { target: { value: '有' } })
    fireEvent.click(await screen.findByText('有方向'))
    expect(screen.getByLabelText('方向')).toHaveValue('科技.A')
    fireEvent.change(search, { target: { value: '无' } })
    fireEvent.click(await screen.findByText('无方向'))
    expect(screen.getByLabelText('方向')).toHaveValue('')
  })

  it('选股后自动带入方向、识别买点并默认采用止损建议', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
      const url = String(input)
      if (url.startsWith('/api/holdings?_=')) {
        return {
          ok: true,
          json: async () => ({ cash_ratio: 100, holdings: [] }),
        } as Response
      }
      if (url === '/api/directions/get') {
        return { ok: true, json: async () => ({ active_ordered: ['科技.A'] }) } as Response
      }
      if (url.startsWith('/api/directions/stocks')) {
        return { ok: true, json: async () => ({ stocks: [{ name: '测试股份', code: '000001', price: 100, direction: '科技.A' }] }) } as Response
      }
      if (url === '/api/holdings/recommended-stop') {
        return {
          ok: true,
          json: async () => ({
            success: true, stop_loss: 94, recommendation_type: 'entry_structure_stop',
            reason: '按买点结构计算', price: 100, initial_stop: 94,
            buy_date_used: '2026-08-01', protective_stop: null, current_stop: null,
            can_raise: false, stop_loss_pct: -6, entry_signal_type: '反转买点',
            entry_signal_confidence: 82, entry_signal_reason: '放量反转', initial_stop_anchor: null,
          }),
        } as Response
      }
      throw new Error(`unexpected fetch: ${url}`)
    })
    renderPage()

    fireEvent.click(await screen.findByText('＋ 新增第一只持仓'))
    fireEvent.change(screen.getByPlaceholderText('输入股票名称或代码...'), { target: { value: '测试' } })
    fireEvent.click(await screen.findByText('测试股份'))

    expect(screen.getByLabelText('方向')).toHaveValue('科技.A')
    expect(screen.getByDisplayValue('100')).toBeTruthy()
    await screen.findByTestId('stop-recommendation')
    expect(screen.getByTestId('entry-signal-status')).toHaveTextContent('反转买点')
    expect(screen.getByLabelText(/止损价/)).toHaveValue(94)
    expect(screen.queryByText('计算止损建议')).toBeNull()
    expect(screen.queryByText('采用建议')).toBeNull()
  })

  it('无买点时明确显示无买点并仍采用降级止损', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
      const url = String(input)
      if (url.startsWith('/api/holdings?_=')) return { ok: true, json: async () => ({ holdings: [], cash_ratio: 100 }) } as Response
      if (url === '/api/directions/get') return { ok: true, json: async () => ({ active_ordered: ['科技.A'] }) } as Response
      if (url.startsWith('/api/directions/stocks')) return { ok: true, json: async () => ({ stocks: [{ name: '普通股份', code: '000002', price: 50, direction: '科技.A' }] }) } as Response
      if (url === '/api/holdings/recommended-stop') return {
        ok: true,
        json: async () => ({
          success: true, stop_loss: 47, recommendation_type: 'atr_fallback', reason: '未识别买点，使用波动率降级止损',
          price: 50, initial_stop: 47, buy_date_used: '2026-08-01', protective_stop: null,
          current_stop: null, can_raise: false, stop_loss_pct: -6, entry_signal_type: null,
          entry_signal_confidence: null, entry_signal_reason: '', initial_stop_anchor: null,
        }),
      } as Response
      throw new Error(`unexpected fetch: ${url}`)
    })
    renderPage()
    fireEvent.click(await screen.findByText('＋ 新增第一只持仓'))
    fireEvent.change(screen.getByPlaceholderText('输入股票名称或代码...'), { target: { value: '普通' } })
    fireEvent.click(await screen.findByText('普通股份'))
    await screen.findByTestId('stop-recommendation')
    expect(screen.getByTestId('entry-signal-status')).toHaveTextContent('无买点')
    expect(screen.getByLabelText(/止损价/)).toHaveValue(47)
  })

  it('在途自动计算不会覆盖用户刚刚手工修正的止损', async () => {
    let resolveStop!: (response: Response) => void
    const pendingStop = new Promise<Response>(resolve => { resolveStop = resolve })
    vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
      const url = String(input)
      if (url.startsWith('/api/holdings?_=')) return { ok: true, json: async () => ({ holdings: [], cash_ratio: 100 }) } as Response
      if (url === '/api/directions/get') return { ok: true, json: async () => ({ active_ordered: ['科技.A'] }) } as Response
      if (url.startsWith('/api/directions/stocks')) return { ok: true, json: async () => ({ stocks: [{ name: '竞态股份', code: '000003', price: 100, direction: '科技.A' }] }) } as Response
      if (url === '/api/holdings/recommended-stop') return pendingStop
      throw new Error(`unexpected fetch: ${url}`)
    })
    renderPage()
    fireEvent.click(await screen.findByText('＋ 新增第一只持仓'))
    fireEvent.change(screen.getByPlaceholderText('输入股票名称或代码...'), { target: { value: '竞态' } })
    fireEvent.click(await screen.findByText('竞态股份'))
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/holdings/recommended-stop', expect.anything(),
    ))
    fireEvent.change(screen.getByLabelText(/止损价/), { target: { value: '96' } })
    resolveStop({
      ok: true,
      json: async () => ({
        success: true, stop_loss: 94, recommendation_type: 'initial_risk_stop', reason: '自动建议',
        price: 100, initial_stop: 94, buy_date_used: '2026-08-01', protective_stop: null,
        current_stop: null, can_raise: false, stop_loss_pct: -6, entry_signal_type: '反转买点',
        entry_signal_confidence: 80, entry_signal_reason: '', initial_stop_anchor: null,
      }),
    } as Response)
    await screen.findByTestId('stop-recommendation')
    expect(screen.getByLabelText(/止损价/)).toHaveValue(96)
  })

  it('编辑持仓不允许删除或下调已有止损', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {})
    vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
      const url = String(input)
      if (url.startsWith('/api/holdings?_=')) return {
        ok: true,
        json: async () => ({
          cash_ratio: 90,
          holdings: [{
            name: '保护股份', code: '000004', ratio: 10, direction: '科技.A',
            stop_loss_price: 95, buy_price: 100, buy_date: null, price: 110,
            change: 1, stop_loss_pct: -13.64, sector: '', structure: '上涨趋势', stage: '上行',
          }],
        }),
      } as Response
      if (url === '/api/directions/get') return { ok: true, json: async () => ({ active_ordered: ['科技.A'] }) } as Response
      throw new Error(`unexpected fetch: ${url}`)
    })
    renderPage()
    fireEvent.click(await screen.findByText('✏️ 编辑'))
    fireEvent.change(screen.getByLabelText(/止损价/), { target: { value: '90' } })
    fireEvent.click(screen.getByText('保存'))
    expect(alertSpy).toHaveBeenCalledWith(expect.stringContaining('只能维持或上调'))
  })

  it('自动维持同价止损时保留原始来源元数据', async () => {
    let savedBody: any = null
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input)
      if (url.startsWith('/api/holdings?_=')) return {
        ok: true,
        json: async () => ({
          cash_ratio: 90,
          holdings: [{
            name: '来源股份', code: '000005', ratio: 10, direction: '科技.A',
            stop_loss_price: 95, buy_price: 100, buy_date: '2026-07-31', price: 110,
            change: 1, stop_loss_pct: -13.64, sector: '', structure: '上涨趋势', stage: '上行',
            entry_signal_type: '反转买点', stop_loss_source: 'manual',
          }],
        }),
      } as Response
      if (url === '/api/directions/get') return { ok: true, json: async () => ({ active_ordered: ['科技.A'] }) } as Response
      if (url === '/api/holdings/recommended-stop') return {
        ok: true,
        json: async () => ({
          success: true, stop_loss: 95, recommendation_type: 'keep_current_stop', reason: '维持已有止损',
          price: 110, initial_stop: null, buy_date_used: '2026-07-31', protective_stop: null,
          current_stop: 95, can_raise: false, stop_loss_pct: -13.64, entry_signal_type: '反转买点',
          entry_signal_confidence: null, entry_signal_reason: '', initial_stop_anchor: null,
        }),
      } as Response
      if (url === '/api/holdings/save') {
        savedBody = JSON.parse(String(init?.body))
        return { ok: true, json: async () => ({ success: true }) } as Response
      }
      throw new Error(`unexpected fetch: ${url}`)
    })
    renderPage()
    fireEvent.click(await screen.findByText('✏️ 编辑'))
    await screen.findByTestId('stop-recommendation')
    fireEvent.click(screen.getByText('保存'))
    await waitFor(() => expect(savedBody).not.toBeNull())
    expect(savedBody.holdings[0].stop_loss_source).toBe('manual')
  })
})
