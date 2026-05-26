/// <reference types="vitest" />
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import MarketCycle from '../components/MarketCycle'
import MainlineSection from '../components/MainlineSection'
import HistoryReview from '../components/HistoryReview'

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
