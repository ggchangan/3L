/// <reference types="vitest" />
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Workbench, {
  buySuggestionAction,
  buySuggestionDestination,
  buySuggestionWatchReason,
  formatYesterdayPlanItem,
  holdingSuggestionDestination,
  suggestionConditionFields,
} from '../pages/Workbench'

function renderWB() {
  return render(<MemoryRouter><Workbench /></MemoryRouter>)
}

describe('Workbench', () => {
  it('只有 executable 复盘信号进入买入计划', () => {
    expect(buySuggestionDestination({ decision_status: 'executable' })).toBe('buy')
    expect(buySuggestionDestination({ decision_status: 'executable', plan_readiness: 'needs_stop' })).toBe('watch')
    expect(buySuggestionDestination({ decision_status: 'candidate' })).toBe('watch')
    expect(buySuggestionDestination({ decision_status: 'signal_only' })).toBe('watch')
    expect(buySuggestionDestination({ decision_status: 'blocked' })).toBe('watch')
    expect(buySuggestionDestination({})).toBe('watch')
  })

  it('持仓加仓缺少止损时进入待完善观察', () => {
    expect(holdingSuggestionDestination({ action: '加仓', plan_readiness: 'needs_stop' })).toBe('watch')
    expect(holdingSuggestionDestination({ action: '加仓', plan_readiness: 'ready' })).toBe('buy')
    expect(holdingSuggestionDestination({ action: '卖出', plan_readiness: 'ready' })).toBe('sell')
  })

  it('观察计划优先保留不可执行原因', () => {
    expect(buySuggestionWatchReason({
      decision_status: 'signal_only',
      attention_reason: '非主线且未进入动量前50，仅保留技术信号',
      reason: '弱势市场→机器人',
    })).toBe('非主线且未进入动量前50，仅保留技术信号')
    expect(buySuggestionWatchReason({ decision_status: 'signal_only' }))
      .toBe('仅为技术信号，不进入核心交易计划')
  })

  it('建议列表以 decision_status 覆盖冲突的旧操作字段', () => {
    expect(buySuggestionAction({ decision_status: 'candidate', action_type: '买入' })).toBe('观察')
    expect(buySuggestionAction({ decision_status: 'signal_only', action_type: '买入' })).toBe('技术信号')
    expect(buySuggestionAction({ decision_status: 'blocked', action_type: '买入' })).toBe('待确认')
    expect(buySuggestionAction({ decision_status: 'executable', action_type: '观察' })).toBe('买入')
    expect(buySuggestionAction({ action_type: '买入' })).toBe('技术信号')
  })

  it('导入计划时保留结构化触发、失效、止损和有效期', () => {
    expect(suggestionConditionFields({
      trigger_condition: '放量突破且不跌回',
      action_when_triggered: '按计划买入',
      invalidation_condition: '突破失败',
      stop_condition: '跌破 10.00 时止损',
      valid_for: '下一交易日',
      plan_readiness: 'ready',
    } as any, '旧买点文案')).toEqual({
      condition: '放量突破且不跌回',
      action_when_triggered: '按计划买入',
      invalidation_condition: '突破失败',
      stop_condition: '跌破 10.00 时止损',
      valid_for: '下一交易日',
      plan_readiness: 'ready',
    })
  })

  it('旧复盘缓存仍回退到原计划条件', () => {
    expect(suggestionConditionFields({}, '中继买点 +1.2%').condition)
      .toBe('中继买点 +1.2%')
  })

  it('次日执行复盘完整回显条件计划并兼容旧观察日志', () => {
    expect(formatYesterdayPlanItem({
      status: 'pending',
      condition: '放量突破且不跌回',
      action_when_triggered: '按计划买入',
      invalidation_condition: '突破失败',
      stop_condition: '跌破 10.00 时止损',
      valid_for: '下一交易日',
    }, 'buy')).toContain('失效：突破失败')
    expect(formatYesterdayPlanItem({ status: 'pending', focus: '等待方向转强' }, 'watch'))
      .toBe('触发：等待方向转强')
  })

  it('渲染标题', () => {
    renderWB()
    expect(screen.getByText('🧑 交易工作台')).toBeTruthy()
  })

  it('渲染所有区块标题', () => {
    renderWB()
    expect(screen.getByText('今日复盘摘要')).toBeTruthy()
    expect(screen.getByText('📋 明日计划')).toBeTruthy()
    expect(screen.getByText('✍️ 今日操作')).toBeTruthy()
    expect(screen.getByText('🔄 执行复盘')).toBeTruthy()
    expect(screen.getByText('💡 今日反思')).toBeTruthy()
  })

  it('渲染日期导航', () => {
    renderWB()
    expect(screen.getByText('← 前一天')).toBeTruthy()
    expect(screen.getByText('后一天 →')).toBeTruthy()
    expect(screen.getByText('💾 保存交易日志')).toBeTruthy()
  })
})
