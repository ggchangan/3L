/// <reference types="vitest" />
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MarketCycle, { classifyMarketRegime, resolveActiveIndexCode, selectReviewIndexData } from '../components/MarketCycle'
import MainlineSection from '../components/MainlineSection'
import HistoryReview from '../components/HistoryReview'
import ReviewDataStatus from '../components/ReviewDataStatus'
import TradingPlan from '../components/TradingPlan'
import { formatSectorEnvironment } from '../lib/review'

// ====== MarketCycle ======
describe('MarketCycle', () => {
  it('loading时显示加载中', () => {
    render(<MarketCycle />)
    expect(screen.getByText('加载中...')).toBeTruthy()
  })

  it('将市场趋势明确归类为强势、震荡或弱势', () => {
    expect(classifyMarketRegime('上涨趋势')).toBe('strong')
    expect(classifyMarketRegime('区间震荡')).toBe('neutral')
    expect(classifyMarketRegime('下降趋势')).toBe('weak')
  })

  it('趋势接口缺失时使用均线关系兜底', () => {
    expect(classifyMarketRegime(undefined, { price: 120, ma20: 110, ma60: 100 })).toBe('strong')
    expect(classifyMarketRegime(undefined, { price: 80, ma20: 90, ma60: 100 })).toBe('weak')
    expect(classifyMarketRegime(undefined, { price: '--' })).toBe('unknown')
  })

  it('复盘模式只保留同一交易日指数，并以复盘快照覆盖中证全指', () => {
    const selected = selectReviewIndexData({
      '000985': { price: 120, data_date: '20260723' },
      '000001': { price: 100, data_date: '20260723' },
      '399006': { price: 90, data_date: '20260722' },
    }, { price: 88, structure: '下降趋势' }, '20260722')

    expect(selected['000985'].price).toBe(88)
    expect(selected['000985'].data_date).toBe('20260722')
    expect(selected['399006'].price).toBe(90)
    expect(selected['000001']).toBeUndefined()
  })

  it('当前指数被日期过滤后自动回退到仍可用的中证全指', () => {
    expect(resolveActiveIndexCode({ '000985': { price: 88 } }, '399006')).toBe('000985')
  })
})

// ====== MainlineSection ======
describe('MainlineSection', () => {
  it('空数据时显示暂无主线', () => {
    render(<MainlineSection data={null} dates={[]} currentDate="" />)
    expect(screen.getByText('暂无主线数据')).toBeTruthy()
  })

  it('按主线层级展示方向，并把波峰波谷保留为板块阶段', () => {
    render(<MainlineSection
      data={{
        lines: [{ name: '主线A', chg_20d: 18, stage: '波峰' }],
        secondary: [{ name: '次线B', chg_20d: 12, stage: '波中' }],
        all_ranked: [
          { name: '主线A', chg_20d: 18, stage: '波峰' },
          { name: '次线B', chg_20d: 12, stage: '波中' },
          { name: '方向C', chg_20d: 8, stage: '波谷' },
        ],
      }}
      dates={[]}
      currentDate="2026-07-23"
    />)

    expect(screen.getByText('主线方向')).toBeTruthy()
    expect(screen.getAllByText('次级主线').length).toBeGreaterThan(0)
    expect(screen.getByText(/波谷是加分项/)).toBeTruthy()
    expect(screen.queryByText('主线回调机会')).toBeNull()
  })
})

// ====== HistoryReview ======
describe('HistoryReview', () => {
  it('空列表时显示暂无历史', () => {
    render(<HistoryReview dates={[]} currentDate="" />)
    expect(screen.getByText('暂无历史复盘数据')).toBeTruthy()
  })

  it('过滤掉当前日期', () => {
    render(<HistoryReview dates={['2026-05-22', '2026-05-21']} currentDate="2026-05-22" />)
    expect(screen.getByText('2026-05-21')).toBeTruthy()
    expect(screen.queryByText('2026-05-22')).toBeNull()
  })
})

// ====== ReviewDataStatus ======
describe('ReviewDataStatus', () => {
  it('显示正式数据和待补齐的行业概念日期', () => {
    render(
      <ReviewDataStatus
        dataStatus={{
          stocks: { status: 'confirmed', date: '20260721' },
          index: { status: 'confirmed', date: '20260721' },
          industry: { status: 'stale', confirmed_date: '20260718' },
          concept: { status: 'unknown' },
        }}
      />,
    )

    expect(screen.getByText('个股 07-21 · 正式数据')).toBeTruthy()
    expect(screen.getByText('指数 07-21 · 正式数据')).toBeTruthy()
    expect(screen.getByText('行业 07-18 · 待补齐')).toBeTruthy()
    expect(screen.getByText(/对应个股暂显示“待确认”/)).toBeTruthy()
  })

  it('行业概念均为正式数据时不显示校准提示', () => {
    render(
      <ReviewDataStatus
        dataStatus={{
          stocks: { status: 'confirmed', date: '20260721' },
          index: { status: 'confirmed', date: '20260721' },
          industry: { status: 'confirmed', date: '20260721' },
          concept: { status: 'confirmed', date: '20260721' },
        }}
      />,
    )

    expect(screen.getByText('行业 07-21 · 正式数据')).toBeTruthy()
    expect(screen.queryByText(/次日 06:00/)).toBeNull()
  })

  it('分别展示行业和概念当日预估覆盖率', () => {
    render(
      <ReviewDataStatus
        dataStatus={{
          stocks: { status: 'confirmed', date: '20260721' },
          index: { status: 'confirmed', date: '20260721' },
          industry: { status: 'estimated', date: '20260721', confirmed_date: '20260720', coverage: 0.9781, coverage_detail: { covered: 312, expected: 319 } },
          concept: { status: 'estimated', date: '20260721', confirmed_date: '20260720', coverage: 0.8533, coverage_detail: { covered: 157, expected: 184 } },
        }}
      />,
    )

    expect(screen.getByText('行业 07-21 · 当日预估 97.8%，312/319')).toBeTruthy()
    expect(screen.getByText('概念 07-21 · 当日预估 85.3%，157/184')).toBeTruthy()
    expect(screen.getByText(/未覆盖个股暂显示“待确认”/)).toBeTruthy()
  })

  it('概念正式日线不完整时显示部分状态和覆盖数', () => {
    render(
      <ReviewDataStatus
        dataStatus={{
          stocks: { status: 'confirmed', date: '20260722' },
          index: { status: 'confirmed', date: '20260722' },
          industry: { status: 'confirmed', date: '20260722' },
          concept: {
            status: 'partial',
            date: '20260722',
            confirmed_date: '20260721',
            coverage: 175 / 179,
            coverage_detail: { covered: 175, expected: 179 },
          },
        }}
      />,
    )

    expect(screen.getByText('概念 07-22 · 部分正式数据 97.8%，175/179')).toBeTruthy()
    expect(screen.getByText(/缺失概念已从当日排名中排除/)).toBeTruthy()
  })
})

describe('TradingPlan action semantics', () => {
  it('在同一列表展示买入和待确认操作', () => {
    render(<TradingPlan plan={{
      buy_priority: [
        { code: '1', name: '执行股', decision_status: 'executable', action_type: '买入' },
        { code: '2', name: '候选股', decision_status: 'candidate', action_type: '买入' },
        { code: '3', name: '阻断股', decision_status: 'blocked', action_type: '待确认' },
      ],
    }} />)

    expect(screen.getByText('🎯 关注买点 (3)')).toBeTruthy()
    expect(screen.getAllByText('买入')).toHaveLength(2)
    expect(screen.getByText('待确认')).toBeTruthy()
    expect(screen.queryByText(/可执行买点/)).toBeNull()
    expect(screen.queryByText(/候选观察/)).toBeNull()
  })
})

describe('板块环境语义', () => {
  it('不把波谷和趋势阶段直接称为机会', () => {
    expect(formatSectorEnvironment('主线回调')).toBe('主线 · 波谷')
    expect(formatSectorEnvironment('次线机会')).toBe('次级主线 · 波谷')
    expect(formatSectorEnvironment('见顶风险', '主线')).toBe('主线 · 波峰风险')
    expect(formatSectorEnvironment('趋势延续')).toBe('板块 · 上升/波中')
  })
})
