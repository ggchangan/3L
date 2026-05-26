/// <reference types="vitest" />
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import StockCard from '../components/StockCard'
import RuleLayer from '../components/RuleLayer'
import type { BuySignalItem } from '../lib/types'
import { fmtAmountYuan, fmtVol, getYesterdayStr } from '../lib/api'

// ====== 工具函数测试 ======
describe('lib/api 工具函数', () => {
  it('fmtAmountYuan 正确格式化亿元', () => {
    expect(fmtAmountYuan(1500000000)).toBe('15.0亿')
    expect(fmtAmountYuan(0)).toBe('0')
    expect(fmtAmountYuan(undefined)).toBe('0')
  })

  it('fmtVol 正确格式化成交量', () => {
    expect(fmtVol(150000000)).toBe('1.5亿')
    expect(fmtVol(50000)).toBe('5万')
    expect(fmtVol(999)).toBe('999')
    expect(fmtVol(undefined)).toBe('0')
  })

  it('getYesterdayStr 返回 YYYY-MM-DD 格式', () => {
    const s = getYesterdayStr()
    expect(s).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
})

// ====== RuleLayer 静态组件测试 ======
describe('RuleLayer', () => {
  it('渲染三条纪律规则', () => {
    render(<RuleLayer />)
    expect(screen.getByText('按计划执行，达到条件才操作')).toBeTruthy()
    expect(screen.getByText('不看分时图，只看日K线')).toBeTruthy()
    expect(screen.getByText('不做T+0，盘中不临时起意')).toBeTruthy()
  })

  it('显示层标题', () => {
    render(<RuleLayer />)
    expect(screen.getByText('⚠️ 今日纪律')).toBeTruthy()
  })
})

// ====== StockCard 组件测试 ======
describe('StockCard', () => {
  const buySignal: BuySignalItem = {
    code: '000001',
    name: '平安银行',
    signal: 'buy',
    stage: '上行',
    structure: '上涨趋势',
    trading_system: '3l',
    buy_point: '涨停回踩EMA10',
    change: 2.5,
    price: 12.34,
    direction: '银行',
    profit_model1: true,
    sector: '银行',
  }

  it('渲染买入信号卡片', () => {
    render(<StockCard s={buySignal} idx={1} />)
    // name 用 class 定位（emoji 拆分导致 getByText 匹配多个）
    const nameEl = document.querySelector('.name')
    expect(nameEl?.textContent).toContain('平安银行')
    expect(screen.getByText('000001')).toBeTruthy()
    expect(screen.getByText(/12.34/)).toBeTruthy()
    expect(screen.getByText('🏆 盈利1')).toBeTruthy()
  })

  it('买点信号显示🎯买点标签', () => {
    render(<StockCard s={buySignal} idx={1} />)
    expect(screen.getByText('🎯 买点')).toBeTruthy()
  })

  it('trend 系统显示区域代替买点', () => {
    const trendSignal: BuySignalItem = {
      ...buySignal,
      trading_system: 'trend',
      trend_bias: 1.5,
      buy_point: '',
    }
    render(<StockCard s={trendSignal} idx={1} />)
    // 区域字段和结论都包含乖离率买入区——改用 container 查找到具体的元素
    const container = document.body
    const els = container.querySelectorAll('[class="v"]')
    const regionEl = Array.from(els).find(el => el.textContent?.includes('乖离率买入区'))
    expect(regionEl).toBeTruthy()
    expect(regionEl?.textContent).toContain('BIAS=1.50%')
  })

  it('持有信号显示✅持有', () => {
    const holdSignal: BuySignalItem = {
      ...buySignal,
      signal: 'hold',
      stage: '缩量整理',
    }
    render(<StockCard s={holdSignal} idx={1} />)
    expect(screen.getByText('✅持有')).toBeTruthy()
  })

  it('显示止损信息', () => {
    const slSignal: BuySignalItem = {
      ...buySignal,
      stop_loss: 11.50,
      stop_loss_pct: 6.8,
    }
    render(<StockCard s={slSignal} idx={1} />)
    // 止损字段用 class 定位
    const container = document.body
    const fieldEls = container.querySelectorAll('.field')
    const slEl = Array.from(fieldEls).find(el => el.textContent?.includes('止损'))
    expect(slEl).toBeTruthy()
    expect(slEl?.textContent).toContain('11.50')
    expect(slEl?.textContent).toContain('6.8%')
  })

  it('趋势股标签', () => {
    const trendTag: BuySignalItem = {
      ...buySignal,
      trend_stock: true,
    }
    render(<StockCard s={trendTag} idx={1} />)
    expect(screen.getByText('📈 趋势股')).toBeTruthy()
  })

  it('主线定位颜色', () => {
    const mainlineSignal: BuySignalItem = {
      ...buySignal,
      mainline_level: '主线',
    }
    render(<StockCard s={mainlineSignal} idx={1} />)
    expect(screen.getByText('主线')).toBeTruthy()
  })

  it('null sector_chg 不崩溃', () => {
    const s: BuySignalItem = {
      ...buySignal,
      sector_chg: null as any,
    }
    render(<StockCard s={s} idx={1} />)
    // 板块文字应该显示，不崩溃
    expect(document.querySelector('.stock-item')).toBeTruthy()
  })

  it('sector_chg 显示板块涨跌幅', () => {
    const s: BuySignalItem = {
      ...buySignal,
      sector: '半导体',
      sector_chg: 3.25,
    }
    render(<StockCard s={s} idx={1} />)
    const fieldEls = document.querySelectorAll('.field')
    const sectorEl = Array.from(fieldEls).find(el => el.textContent?.includes('板块'))
    expect(sectorEl).toBeTruthy()
    expect(sectorEl?.textContent).toContain('半导体')
    expect(sectorEl?.textContent).toContain('+3.25%')
  })

  it('direction 单独显示', () => {
    const s: BuySignalItem = {
      ...buySignal,
      sector: '银行',
      direction: '银行方向',
      sector_chg: 1.0,
    }
    render(<StockCard s={s} idx={1} />)
    const fieldEls = document.querySelectorAll('.field')
    const sectorEl = Array.from(fieldEls).find(el => el.textContent?.includes('方向'))
    expect(sectorEl).toBeTruthy()
    expect(sectorEl?.textContent).toContain('银行方向')
  })

  it('null trend_bias 不崩溃（非趋势系统）', () => {
    const s: BuySignalItem = {
      ...buySignal,
      trading_system: 'trend',
      trend_bias: null as any,
    }
    render(<StockCard s={s} idx={1} />)
    // 不应该抛出异常
    expect(document.querySelector('.stock-item')).toBeTruthy()
  })
})
