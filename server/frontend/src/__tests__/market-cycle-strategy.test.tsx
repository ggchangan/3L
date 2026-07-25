/// <reference types="vitest" />
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

vi.mock('../lib/api', () => ({
  INDEX_CODES_LIST: ['000985'],
  INDEX_CODE_NAMES: { '000985': '中证全指' },
  fetchAllIndexData: vi.fn().mockResolvedValue({
    '000985': {
      price: 5200,
      change: -1,
      position: '波中',
      structure: '下降趋势',
      market_regime: 'weak',
      data_date: '20260724',
    },
  }),
}))

import MarketCycle from '../components/MarketCycle'

describe('MarketCycle dynamic position strategy', () => {
  it('弱势主跌场景展示真实仓位和交易节奏，不展示静态建议仓位', async () => {
    render(
      <MarketCycle
        reviewMarket={{ position: '波中', structure: '下降趋势', market_regime: 'weak' }}
        reviewIndexDate="20260724"
        marketStrategy={{
          environment: 'weak', environment_label: '弱势市场',
          risk_phase: 'main_decline', risk_label: '主跌风险',
          wave_phase: '波中', wave_label: '波中',
          position_mode: 'defensive', position_action: '暂停新增仓位，先执行卖出与止损计划',
          current_position_pct: 50, planned_exit_pct: 10, position_after_exits_pct: 40,
          executable_buy_count: 0,
          allowed_buy_points: ['恐慌买点', '供应衰竭买点', '明确反转买点'],
          avoid_buy_points: ['普通突破追涨'],
          holding_style: '缩短交易周期，只保留强方向和强个股',
          exit_style: '收紧止盈和止损',
          summary: '弱势市场 · 主跌风险', basis: [],
        }}
      />,
    )

    expect(await screen.findByText('弱势市场')).toBeTruthy()
    expect(screen.getByText('风险阶段：主跌风险')).toBeTruthy()
    expect(screen.getByText('50% → 40%')).toBeTruthy()
    expect(screen.getByText('明确卖出 10%')).toBeTruthy()
    expect(screen.getByText(/适用买点：恐慌买点、供应衰竭买点、明确反转买点/)).toBeTruthy()
    expect(screen.queryByText(/建议仓位/)).toBeNull()
    expect(screen.queryByText(/七至八成/)).toBeNull()
  })
})
