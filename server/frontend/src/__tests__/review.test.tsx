/// <reference types="vitest" />
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MarketCycle from '../components/MarketCycle'
import MainlineSection from '../components/MainlineSection'
import HistoryReview from '../components/HistoryReview'
import ReviewDataStatus from '../components/ReviewDataStatus'
import TradingPlan from '../components/TradingPlan'

// ====== MarketCycle ======
describe('MarketCycle', () => {
  it('loading时显示加载中', () => {
    render(<MarketCycle />)
    expect(screen.getByText('加载中...')).toBeTruthy()
  })
})

// ====== MainlineSection ======
describe('MainlineSection', () => {
  it('空数据时显示暂无主线', () => {
    render(<MainlineSection data={null} dates={[]} currentDate="" />)
    expect(screen.getByText('暂无主线数据')).toBeTruthy()
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
    expect(screen.getByText(/不可作为交易指令/)).toBeTruthy()
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
    expect(screen.getByText(/未覆盖项目已阻断交易指令/)).toBeTruthy()
  })
})

describe('TradingPlan decision gate', () => {
  it('分开展示可执行、候选和数据阻断项目', () => {
    render(<TradingPlan plan={{
      buy_priority: [
        { code: '1', name: '执行股', decision_status: 'executable', action_type: '买入' },
        { code: '2', name: '候选股', decision_status: 'candidate', action_type: '买入' },
        { code: '3', name: '阻断股', decision_status: 'blocked', action_type: '待确认' },
      ],
    }} />)

    expect(screen.getByText('✅ 可执行买点 (1)')).toBeTruthy()
    expect(screen.getByText('👀 候选观察 (1)')).toBeTruthy()
    expect(screen.getByText('⛔ 数据阻断 (1)')).toBeTruthy()
    expect(screen.getByText('可执行')).toBeTruthy()
    expect(screen.getByText('候选')).toBeTruthy()
    expect(screen.getByText('待确认')).toBeTruthy()
  })
})
