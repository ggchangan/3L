/// <reference types="vitest" />
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MarketCycle from '../components/MarketCycle'
import MainlineSection from '../components/MainlineSection'
import HistoryReview from '../components/HistoryReview'
import ReviewDataStatus from '../components/ReviewDataStatus'

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
  it('显示已确认数据和待补齐的板块日期', () => {
    render(
      <ReviewDataStatus
        data_dates={{ stocks: '20260721', index: '20260721', sectors: '20260718' }}
        data_freshness={{ stocks: 'current', index: 'current', sectors: 'stale' }}
      />,
    )

    expect(screen.getByText('个股 07-21 · 已确认')).toBeTruthy()
    expect(screen.getByText('指数 07-21 · 已确认')).toBeTruthy()
    expect(screen.getByText('板块 07-18 · 待补齐')).toBeTruthy()
    expect(screen.getByText(/次日 06:00 自动校准/)).toBeTruthy()
  })

  it('板块已确认时不显示校准提示', () => {
    render(
      <ReviewDataStatus
        data_dates={{ stocks: '2026-07-21', index: '2026-07-21', sectors: '2026-07-21' }}
        data_freshness={{ stocks: 'current', index: 'current', sectors: 'current' }}
      />,
    )

    expect(screen.getByText('板块 07-21 · 已确认')).toBeTruthy()
    expect(screen.queryByText(/次日 06:00 自动校准/)).toBeNull()
  })
})