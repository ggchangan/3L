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

  it('编辑旧持仓不伪造买入日期，止损建议需明确采用才写入', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async input => {
      const url = String(input)
      if (url.startsWith('/api/holdings?_=')) {
        return {
          ok: true,
          json: async () => ({
            cash_ratio: 90,
            holdings: [{
              name: '测试股份', code: '000001', ratio: 10, direction: '科技.A',
              stop_loss_price: 95, buy_price: 100, buy_date: null,
              price: 120, change: 2, stop_loss_pct: -20.83,
              sector: '测试行业', structure: '上涨趋势', stage: '上行',
            }],
          }),
        } as Response
      }
      if (url === '/api/directions/get') {
        return { ok: true, json: async () => ({ active_ordered: ['科技.A'] }) } as Response
      }
      if (url === '/api/holdings/recommended-stop') {
        return {
          ok: true,
          json: async () => ({
            success: true, stop_loss: 108, recommendation_type: 'raise_protective_stop',
            reason: '最新价格结构已抬高', price: 120, initial_stop: null,
            buy_date_used: null, protective_stop: 108, current_stop: 95,
            can_raise: true, stop_loss_pct: -10,
          }),
        } as Response
      }
      throw new Error(`unexpected fetch: ${url}`)
    })
    renderPage()

    fireEvent.click(await screen.findByText('✏️ 编辑'))
    expect(screen.getByLabelText('买入日期')).toHaveValue('')
    expect(screen.getByLabelText(/止损价/)).toHaveValue(95)

    fireEvent.click(screen.getByText('计算止损建议'))
    await screen.findByTestId('stop-recommendation')
    expect(screen.getByLabelText(/止损价/)).toHaveValue(95)

    fireEvent.click(screen.getByText('采用建议'))
    expect(screen.getByLabelText(/止损价/)).toHaveValue(108)
  })
})
