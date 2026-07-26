/// <reference types="vitest" />
import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'

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

import MarketCycle, { buildMarketDimensionInfo, selectReviewIndexData } from '../components/MarketCycle'

describe('MarketCycle dynamic position strategy', () => {
  it('市场温度展示原始证据、数据状态和知识库口径', async () => {
    render(
      <MarketCycle
        reviewMarket={{
          position: '波中', structure: '下降趋势', market_regime: 'weak',
          temperature: {
            level: 'ice', label: '冰点观察', status: 'confirmed', date: '20260724', source: 'tushare_mysql',
            metrics: {
              total: 5526, up: 555, down: 4940, flat: 31,
              limit_up: 43, limit_down: 25, new_high_1y: 7, new_low_1y: 232,
              amount_yi: 19444.6, amount_vs_5d_pct: -8.2,
            },
            evidence: ['一年新高仅7家，低于知识库冰点参考线20家', '下跌家数占比89.4%，亏钱效应明显'],
            quality: { stock_count: 5526, limit_covered: 5526, adj_factor_covered: 5526, year_comparable: 5396, missing: [] },
            rules: [{ name: '冰点参考', rule: '一年新高少于20家', origin: '3L训练营' }],
          },
        }}
        reviewIndexDate="20260724"
      />,
    )

    expect(await screen.findByText('冰点观察')).toBeTruthy()
    expect(screen.getByText('555 / 4940 / 31')).toBeTruthy()
    expect(screen.getByText('43 / 25')).toBeTruthy()
    expect(screen.getByText('7 / 232')).toBeTruthy()
    expect(screen.getByText('19444.6亿')).toBeTruthy()
    expect(screen.getByText(/知识库冰点参考线20家/)).toBeTruthy()
    expect(screen.getByText('数据完整')).toBeTruthy()
  })

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
    expect(screen.getByText('市场环境')).toBeTruthy()
    expect(screen.getByText('风险阶段')).toBeTruthy()
    expect(screen.getByText('主跌风险')).toBeTruthy()
    expect(screen.getByText('波段位置')).toBeTruthy()
    expect(screen.getAllByText('波中').length).toBeGreaterThan(0)
    expect(screen.getByText('50% → 40%')).toBeTruthy()
    expect(screen.getByText('明确卖出 10%')).toBeTruthy()
    expect(screen.getByText(/适用买点：恐慌买点、供应衰竭买点、明确反转买点/)).toBeTruthy()
    expect(screen.queryByText(/建议仓位/)).toBeNull()
    expect(screen.queryByText(/七至八成/)).toBeNull()
  })

  it('旧缓存缺少市场策略时风险阶段明确降级为待确认', async () => {
    const { container } = render(
      <MarketCycle
        reviewMarket={{ position: '波中', structure: '下降趋势', market_regime: 'weak' }}
        reviewIndexDate="20260724"
      />,
    )

    expect(await screen.findByText('待确认')).toBeTruthy()
    expect(screen.getByText('风险阶段')).toBeTruthy()
    expect(screen.getByText('波段位置')).toBeTruthy()
    expect(screen.getAllByText('波中').length).toBeGreaterThan(0)
    expect(container.querySelector('.market-dimension.risk.unknown')).toBeTruthy()
    expect(screen.getByText('供需证据不可用')).toBeTruthy()
    expect(screen.getByText(/旧缓存或数据不足/)).toBeTruthy()
  })

  it('V3未形成峰谷方向时同时展示双侧证据，不伪装成波谷', async () => {
    render(
      <MarketCycle
        reviewMarket={{
          position: '波中', wave_side: 'none', wave_phase: 'none', wave_label: '波中',
          structure: '区间震荡', market_regime: 'neutral', algorithm_version: 'supply_demand_v3',
          context: { low_location: 20, high_location: 35 },
          evidence: { supply_exhaustion: 10, demand_exhaustion: 30, absorption: 5, distribution: 25, demand_entry: 8, supply_entry: 12 },
        }}
        reviewIndexDate="20260724"
      />,
    )

    expect(await screen.findByText('未形成')).toBeTruthy()
    expect(screen.getByText('供需衰竭')).toBeTruthy()
    expect(screen.getByText('努力与结果')).toBeTruthy()
    expect(screen.getByText('反向力量')).toBeTruthy()
    expect(screen.getByText(/低 20\/100 \/ 高 35\/100/)).toBeTruthy()
    expect(screen.getByText(/当前未形成峰谷方向/)).toBeTruthy()
  })

  it('三个重要判断可分别展开规则、当前值和本次结论', async () => {
    render(
      <MarketCycle
        reviewMarket={{
          price: 5687.26, ma20: 6110.18, ma60: 6323.48, bias20: -6.92,
          position: '波中偏下', wave_side: 'valley', wave_phase: 'left', wave_label: '波谷左侧',
          structure: '下降趋势', market_regime: 'weak', algorithm_version: 'supply_demand_v3',
          supply_demand_state: '供应仍占优',
          context: { low_location: 57.2, high_location: 0, decline_context: 50.7 },
          evidence: { supply_exhaustion: 54.7, demand_exhaustion: 0, absorption: 0, distribution: 0, demand_entry: 0, supply_entry: 64.3 },
          features: { ma20_slope_5d: -3.0617 },
          explanation: ['市场结构：下降趋势', '价格已进入低位区域', '需求尚未形成有效反转'],
          hard_gates: ['下降趋势尚无有效吸收/放量滞跌', '下降趋势尚无需求进入'],
        }}
        reviewIndexDate="20260724"
        marketStrategy={{
          environment: 'weak', environment_label: '弱势市场',
          risk_phase: 'main_decline', risk_label: '主跌风险',
          wave_phase: 'left', wave_label: '波谷左侧',
          position_mode: 'defensive', position_action: '暂停新增仓位',
          current_position_pct: 50, planned_exit_pct: 0, position_after_exits_pct: 50,
          executable_buy_count: 0, allowed_buy_points: [], avoid_buy_points: [],
          holding_style: '防守', exit_style: '按卖点退出', summary: '', basis: [],
        }}
      />,
    )

    const environmentButton = await screen.findByRole('button', { name: '查看市场环境判断依据' })
    fireEvent.click(environmentButton)
    const environmentPanel = screen.getByRole('region', { name: '市场环境：弱势环境判断详情' })
    expect(screen.getByRole('button', { name: '收起市场环境判断依据' })).toBeTruthy()
    expect(within(environmentPanel).getByText('5687.26')).toBeTruthy()
    expect(within(environmentPanel).getByText('-3.06%')).toBeTruthy()
    expect(within(environmentPanel).getByText(/空头排列/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '查看风险阶段判断依据' }))
    const riskPanel = screen.getByRole('region', { name: '风险阶段：主跌风险判断详情' })
    expect(within(riskPanel).getByText('50.7/100（门槛45）')).toBeTruthy()
    expect(within(riskPanel).getByText('64.3/100（门槛55）')).toBeTruthy()
    expect(within(riskPanel).getByText(/弱势环境本身不等于主跌/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '查看波段位置判断依据' }))
    const wavePanel = screen.getByRole('region', { name: '波段位置：波谷左侧判断详情' })
    expect(within(wavePanel).getByText('57.2/100 / 0.0/100')).toBeTruthy()
    expect(within(wavePanel).getByText(/下降趋势尚无需求进入/)).toBeTruthy()
    expect(screen.queryByRole('region', { name: '风险阶段：主跌风险判断详情' })).toBeNull()
  })

  it('旧缓存和V3 fallback不伪装成完整供需算法解释', () => {
    const legacyRisk = buildMarketDimensionInfo('risk', {
      structure: '下降趋势', position: '波中', pk_score: 1, vl_score: 2, bias20: -5,
    }, {
      environment: 'weak', environment_label: '弱势市场', risk_phase: 'main_decline', risk_label: '主跌风险',
      wave_phase: '波中', wave_label: '波中', position_mode: 'defensive', position_action: '暂停新增',
      current_position_pct: null, planned_exit_pct: null, position_after_exits_pct: null,
      executable_buy_count: 0, allowed_buy_points: [], avoid_buy_points: [], holding_style: '', exit_style: '', summary: '', basis: [],
    })
    expect(legacyRisk.rule.join('')).toContain('兼容判定主跌')
    expect(legacyRisk.rule.join('')).not.toContain('下降背景分 ≥ 45')
    expect(legacyRisk.values).toContainEqual({ label: 'pk_score / vl_score', value: '1 / 2' })

    const fallbackWave = buildMarketDimensionInfo('wave', {
      algorithm_version: 'supply_demand_v3_fallback', position: '波中偏下', pk_score: 0, vl_score: 0,
    })
    expect(fallbackWave.conclusion).toContain('不对旧结果补造解释')
    expect(fallbackWave.values.some(item => item.label === '需求 / 供应进入')).toBe(false)
  })

  it('风险升高面板能解释波峰阶段和严重正乖离两条路径', () => {
    const peakInfo = buildMarketDimensionInfo('risk', {
      algorithm_version: 'supply_demand_v3', structure: '上涨趋势',
      wave_side: 'peak', wave_phase: 'biased', bias20: 5,
      context: { decline_context: 0 }, evidence: { supply_entry: 70 },
    }, {
      environment: 'strong', environment_label: '强势市场', risk_phase: 'risk_rising', risk_label: '风险升高',
      wave_phase: 'biased', wave_label: '偏波峰', position_mode: 'reduce', position_action: '不追高',
      current_position_pct: null, planned_exit_pct: null, position_after_exits_pct: null,
      executable_buy_count: 0, allowed_buy_points: [], avoid_buy_points: [], holding_style: '', exit_style: '', summary: '', basis: [],
    })
    expect(peakInfo.values).toContainEqual({ label: '峰谷方向 / 阶段', value: '波峰 / biased' })
    expect(peakInfo.conclusion).toContain('波峰供需风险')

    const biasInfo = buildMarketDimensionInfo('risk', {
      algorithm_version: 'supply_demand_v3', structure: '区间震荡',
      wave_side: 'none', wave_phase: 'none', bias20: 13.2,
    }, {
      environment: 'neutral', environment_label: '震荡市场', risk_phase: 'risk_rising', risk_label: '风险升高',
      wave_phase: 'none', wave_label: '波中', position_mode: 'reduce', position_action: '不追高',
      current_position_pct: null, planned_exit_pct: null, position_after_exits_pct: null,
      executable_buy_count: 0, allowed_buy_points: [], avoid_buy_points: [], holding_style: '', exit_style: '', summary: '', basis: [],
    })
    expect(biasInfo.values).toContainEqual({ label: 'BIAS20', value: '13.20%' })
    expect(biasInfo.conclusion).toContain('严重正乖离')
  })

  it('环境标题和结论使用同一个结构结论，忽略冲突的缓存标签', () => {
    const info = buildMarketDimensionInfo('environment', {
      algorithm_version: 'supply_demand_v3', market_regime: 'strong', structure: '下降趋势',
      price: 90, ma20: 100, ma60: 110, features: { ma20_slope_5d: -1 },
    })
    expect(info.title).toBe('市场环境：弱势环境')
    expect(info.conclusion).toContain('空头排列')
  })

  it('显式legacy复盘不继承同日实时V3供需字段', () => {
    const selected = selectReviewIndexData({
      '000985': {
        data_date: '20260724', algorithm_version: 'supply_demand_v3',
        wave_label: '波谷左侧', supply_demand_state: '供应仍占优',
        context: { low_location: 57 }, evidence: { supply_entry: 64 },
      },
    }, {
      data_date: '20260724', algorithm_version: 'legacy_bias20_v5', position: '波中',
    }, '20260724')

    expect(selected['000985'].algorithm_version).toBe('legacy_bias20_v5')
    expect(selected['000985'].position).toBe('波中')
    expect(selected['000985'].wave_label).toBeUndefined()
    expect(selected['000985'].context).toBeUndefined()
    expect(selected['000985'].supply_demand_state).toBeUndefined()
  })
})
