/// <reference types="vitest" />
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import TrendCandidates from '../pages/TrendCandidates'

function renderTC() {
  return render(<MemoryRouter><TrendCandidates /></MemoryRouter>)
}

describe('TrendCandidates', () => {
  it('渲染标题', () => {
    renderTC()
    expect(screen.getByText('🎯 趋势交易候选')).toBeTruthy()
  })

  it('渲染搜索框', () => {
    renderTC()
    expect(screen.getByPlaceholderText('🔍 从自选股搜索加入趋势跟踪...')).toBeTruthy()
  })
})
