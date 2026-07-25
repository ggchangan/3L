/// <reference types="vitest" />
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Workbench, { buySuggestionAction, buySuggestionDestination, buySuggestionWatchReason } from '../pages/Workbench'

function renderWB() {
  return render(<MemoryRouter><Workbench /></MemoryRouter>)
}

describe('Workbench', () => {
  it('只有 executable 复盘信号进入买入计划', () => {
    expect(buySuggestionDestination({ decision_status: 'executable' })).toBe('buy')
    expect(buySuggestionDestination({ decision_status: 'candidate' })).toBe('watch')
    expect(buySuggestionDestination({ decision_status: 'signal_only' })).toBe('watch')
    expect(buySuggestionDestination({ decision_status: 'blocked' })).toBe('watch')
    expect(buySuggestionDestination({})).toBe('watch')
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
