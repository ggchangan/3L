/// <reference types="vitest" />
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import MarketCycle, { classifyMarketRegime, resolveActiveIndexCode, selectReviewIndexData } from '../components/MarketCycle'
import MainlineSection from '../components/MainlineSection'
import HistoryReview from '../components/HistoryReview'
import ReviewDataStatus from '../components/ReviewDataStatus'
import TradingPlan from '../components/TradingPlan'
import HoldingsReview, { RiskExposurePanel } from '../components/HoldingsReview'
import { formatSectorEnvironment } from '../lib/review'
import { fetchReviewByDate } from '../lib/api'

vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>()
  return { ...actual, fetchReviewByDate: vi.fn() }
})

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
  beforeEach(() => vi.mocked(fetchReviewByDate).mockReset())

  it('空数据时显示暂无板块强度数据', () => {
    render(<MainlineSection data={null} dates={[]} currentDate="" />)
    expect(screen.getByText('暂无板块强度数据')).toBeTruthy()
  })

  it('按20日板块强度候选分层，并把波峰波谷保留为板块阶段', () => {
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

    expect(screen.getByText('20日强度前5候选')).toBeTruthy()
    expect(screen.getByText('20日强度6–10候选')).toBeTruthy()
    expect(screen.getByText(/波谷是加分项/)).toBeTruthy()
    expect(screen.queryByText('主线回调机会')).toBeNull()
  })

  it('严格使用交易日历给出的上一交易日归档运行轮动比较', async () => {
    vi.mocked(fetchReviewByDate).mockResolvedValue({
      mainline: { all_ranked: [{ name: '旧方向', chg_20d: 10 }] },
    })
    render(<MainlineSection
      data={{
        lines: [{ name: '新方向', chg_20d: 20 }],
        all_ranked: [{ name: '新方向', chg_20d: 20 }],
      }}
      dates={['2026-07-24', '2026-07-22', '2026-07-21']}
      currentDate="2026-07-23"
      previousTradingDate="2026-07-22"
    />)

    await waitFor(() => expect(fetchReviewByDate).toHaveBeenCalledWith('2026-07-22'))
    expect(await screen.findByText(/对比 2026-07-22/)).toBeTruthy()
    expect(screen.getByText(/新进前10: 新方向/)).toBeTruthy()
    expect(screen.getByText(/跌出前10: 旧方向/)).toBeTruthy()
  })

  it('缺少上一交易日归档时不使用更早快照冒充轮动比较', async () => {
    render(<MainlineSection
      data={{ all_ranked: [{ name: '方向A', chg_20d: 10 }] }}
      dates={['2026-07-24', '2026-07-23']}
      currentDate="2026-07-23"
      previousTradingDate="2026-07-22"
    />)

    expect(await screen.findByText('缺少上一交易日复盘，轮动比较待建立')).toBeTruthy()
    expect(fetchReviewByDate).not.toHaveBeenCalled()
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
  it('突出重点和次级观察，并默认折叠普通技术信号', () => {
    render(<TradingPlan plan={{
      buy_priority: [
        {
          code: '1', name: '重点股', attention_tier: 'focus', decision_status: 'executable',
          action_type: '买入', momentum_rank: 4, momentum_total: 319,
          momentum_source: '行业', momentum_direction: '半导体', score: 4,
          quality_score: 80, quality_basis: '3L买点等级',
        },
        { code: '2', name: '观察股', attention_tier: 'watch', decision_status: 'candidate', action_type: '买入' },
        {
          code: '3', name: '普通信号股', attention_tier: 'ordinary', decision_status: 'signal_only',
          action_type: '买入', momentum_rank: 137, momentum_total: 319,
          momentum_source: '行业', momentum_direction: '消费电子',
          quality_score: 66.57076461728134, quality_basis: '多信号融合置信度',
        },
      ],
      buy_summary: {
        total: 3, focus: 1, watch: 1, ordinary: 1, market_regime: 'weak',
        conclusion: '当前为弱势市场，重点买点也需等待确认并控制仓位。',
        ranking_rule: '市场过滤 → 主线/强动量 → 个股买点质量 → 板块环境 → 止损风险',
      },
    }} />)

    expect(screen.getByText('🎯 今日买点重点')).toBeTruthy()
    expect(screen.getByText('重点 1')).toBeTruthy()
    expect(screen.getByText('次级观察 1')).toBeTruthy()
    expect(screen.getByText('普通信号 1')).toBeTruthy()
    expect(screen.getByText('🔥 重点关注 (1)')).toBeTruthy()
    expect(screen.getByText('👀 次级观察 (1)')).toBeTruthy()
    expect(screen.getByText('观察')).toBeTruthy()
    expect(screen.getByText('指标说明：如何理解动量与质量？')).toBeTruthy()
    expect(screen.getByText('动量第4/319（前2%）')).toBeTruthy()
    expect(screen.getByText('质量80/100')).toBeTruthy()
    expect(screen.queryByText('普通信号股')).toBeNull()

    fireEvent.click(screen.getByRole('button', { name: '展开普通技术信号 (1)' }))
    expect(screen.getByText('普通信号股')).toBeTruthy()
    expect(screen.getByText('技术信号')).toBeTruthy()
    const momentum = screen.getByText('动量第137/319（前43%）')
    expect(momentum.getAttribute('title')).toContain('行业动量榜')
    expect(momentum.getAttribute('title')).toContain('匹配方向：消费电子')
    const quality = screen.getByText('质量67/100')
    expect(quality.getAttribute('title')).toContain('不是上涨概率')
    expect(quality.getAttribute('title')).toContain('多信号融合置信度')
  })

  it('旧缓存没有分层字段时保守归入普通信号', () => {
    render(<TradingPlan plan={{
      buy_priority: [
        { code: '1', name: '旧缓存股票', decision_status: 'executable', action_type: '买入', momentum_rank: 3 },
      ],
    }} />)

    expect(screen.getByText('重点 0')).toBeTruthy()
    expect(screen.getByText('普通信号 1')).toBeTruthy()
    expect(screen.getByText('历史缓存未按当前规则重新分层，动量名次仅供参考。')).toBeTruthy()
    expect(screen.queryByText('🔥 重点关注 (1)')).toBeNull()
    expect(screen.queryByText('旧缓存股票')).toBeNull()
  })
})

describe('持仓真实风险暴露', () => {
  it('展示到止损的组合风险、覆盖率和集中度', () => {
    render(<RiskExposurePanel exposure={{
      status: 'partial', basis: '按记录仓位计算',
      total_position_pct: 30, cash_pct: 70,
      stop_covered_position_pct: 20, uncovered_position_pct: 10,
      breached_position_pct: 0, unassessable_position_pct: 0,
      portfolio_downside_to_stops_pct: 2.5,
      largest_position: { code: '000001', name: '平安银行', position_pct: 20 },
      direction_concentration: [{ name: '银行', position_pct: 20 }],
      breached_stop_codes: ['000002'], stop_warnings: [], missing: ['1只缺少有效止损'],
      items: [{
        code: '000001', name: '平安银行', direction: '银行', position_pct: 20,
        cost_price: 10, current_price: 12, stop_loss: 10.8,
        downside_to_stop_pct: 10, portfolio_risk_pct: 2,
        unrealized_pnl_pct: 20,
        stop_status: 'covered',
      }],
    }} />)

    expect(screen.getByText('持仓真实风险暴露')).toBeTruthy()
    expect(screen.getByText('2.50%')).toBeTruthy()
    expect(screen.getByText(/未设 10.0% · 无价格 0.0%/)).toBeTruthy()
    expect(screen.getByText(/最大单股：平安银行 20.0%/)).toBeTruthy()
    expect(screen.getByText(/已跌破止损：000002/)).toBeTruthy()
  })

  it('所有持仓卡片失败时仍展示风险数据缺口', () => {
    render(<HoldingsReview stocks={[]} exposure={{
      status: 'partial', basis: '按记录仓位计算',
      total_position_pct: 20, cash_pct: 80,
      stop_covered_position_pct: 0, breached_position_pct: 0, unassessable_position_pct: 20, uncovered_position_pct: 0,
      portfolio_downside_to_stops_pct: 0,
      largest_position: { code: '000001', name: '平安银行', position_pct: 20 },
      direction_concentration: [{ name: '银行', position_pct: 20 }],
      breached_stop_codes: [], stop_warnings: [], missing: ['1只缺少当日价格'],
      items: [{
        code: '000001', name: '平安银行', direction: '银行', position_pct: 20,
        cost_price: 10, current_price: null, stop_loss: null,
        downside_to_stop_pct: null, portfolio_risk_pct: null,
        unrealized_pnl_pct: null, stop_status: 'missing',
      }],
    }} />)

    expect(screen.getByText('持仓真实风险暴露')).toBeTruthy()
    expect(screen.getByText(/持仓卡片暂不可用/)).toBeTruthy()
    expect(screen.getByText(/数据缺口：1只缺少当日价格/)).toBeTruthy()
  })
})

describe('板块环境语义', () => {
  it('不把波谷和趋势阶段直接称为机会', () => {
    expect(formatSectorEnvironment('主线回调')).toBe('20日强度前5候选 · 波谷')
    expect(formatSectorEnvironment('次线机会')).toBe('20日强度6–10候选 · 波谷')
    expect(formatSectorEnvironment('见顶风险', '主线')).toBe('20日强度前5候选 · 波峰风险')
    expect(formatSectorEnvironment('趋势延续')).toBe('板块 · 上升/波中')
  })
})
