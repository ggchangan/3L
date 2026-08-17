/** 成交额对比API返回类型 */
export interface VolumeData {
  current_price?: number
  current_change?: number
  today_amount_yuan?: number
  amount_ratio?: number
  yesterday_amount_yuan?: number
  yesterday_date?: string
  yesterday_is_estimated?: boolean
  today_curve?: { time: string; amount: number }[]
  current_time?: string
  update_time?: string
  is_trading?: boolean
  yesterday_unavailable?: boolean
  data_source?: { quote?: string; yesterday?: string; yesterday_curve?: string }
}

/** 板块监测API返回类型 */
export interface SectorData {
  industry: {
    today_top5: SectorItem[]
    chg20d_top10: SectorItem[]
  }
  concept: {
    today_top5: SectorItem[]
    chg20d_top10: SectorItem[]
  }
  /** 兼容旧版（后端 data={industry,concept} 嵌套前，fallback） */
  today_top5?: SectorItem[]
  chg20d_top10?: SectorItem[]
  meta?: MonitorMeta
}

export interface MonitorMeta {
  updated_at?: string
  refresh_seconds?: number
  source?: string
  concept_data_date?: string
  concept_available?: boolean
  concept_stale?: boolean
}

export interface SectorItem {
  name: string
  chg?: number
  chg20d?: number
  structure?: string
  phase?: string
}

/** 行业龙头API返回类型 */
export interface LeadersData {
  by_industry?: Record<string, LeaderItem[]>
}

export interface LeaderItem {
  name: string
  chg: number | string
  price: number | string
  mcap: number | string
}

/** 市场龙头API返回类型 */
export interface MarketLeadersData {
  leaders?: MarketLeaderItem[]
  scan_time?: string
  total_industries?: number
}

export interface MarketLeaderItem {
  industry: string
  name: string
  gain_5d: number
  change_pct: number
  turnover_rate: number
  ma10_up: boolean
  price: number
}

/** 龙头观测新面板API返回类型 */
export interface LeaderDashboardData {
  watched: WatchedIndustryItem[]
  anomalies: AnomalyData
  concept_anomalies?: {
    surge: ConceptAnomalyItem[]
    plunge: ConceptAnomalyItem[]
  }
  error?: string
  meta?: MonitorMeta
}

export interface ConceptAnomalyItem {
  name: string
  chg: number
  structure?: string
  phase?: string
}

export interface WatchedIndustryItem {
  industry: string
  leader_name: string
  leader_code: string
  chg: number
  price: number
  mcap: number
  marks: string[]
  switching: SwitchingInfo | null
  divergence: DivergenceInfo | null
  source_tags: string[]
}

export interface SwitchingInfo {
  runner_up_name: string
  runner_up_chg: number
  leader_chg: number
  diff: number
}

export interface DivergenceInfo {
  leader_chg: number
  sector_avg_chg: number
}

export interface AnomalyData {
  surge: AnomalyItem[]
  plunge: AnomalyItem[]
  switching: SwitchingEvent[]
}

export interface AnomalyItem {
  industry: string
  name: string
  code: string
  chg: number
  price: number
  turnover_rate: number
}

export interface SwitchingEvent {
  industry: string
  leader_name: string
  leader_chg: number
  challenger_name: string
  challenger_chg: number
  diff: number
  direction: string
}

/** 买点信号API返回类型 */
export interface BuySignalsData {
  signals?: BuySignalItem[]
  scan_time?: string
  stocks_scanned?: number
}

export interface BuySignalItem {
  decision?: {
    action: string
    signal: string
    priority: string
    reason: string
    stop_loss?: number | null
    stop_loss_pct?: number | null
    version: string
    parameter_version: string
  }
  code: string
  name: string
  signal: 'buy' | 'sell' | 'hold'
  technical_signal?: 'buy' | 'sell' | 'hold'
  execution_signal?: 'buy' | 'sell' | 'hold'
  technical_confidence?: number
  technical_reason?: string
  stage: string
  structure: string
  trading_system?: '3l' | 'trend'
  buy_point?: string
  stop_loss?: number
  stop_loss_price?: number  // 真实API字段名（review返回的数据）
  stop_loss_pct?: number
  profit_model1?: boolean
  trend_stock?: boolean
  trend_bias?: number
  direction?: string
  change?: number
  score?: number
  price?: number
  date?: string
  vol_analysis?: string
  industry?: string
  sector?: string
  sector_chg?: number
  mainline_level?: string
  matched_mainline_direction?: string
  trading_reason?: string
  /** 融合判定字段 */
  triggered_signals?: Array<{
    key: string
    name: string
    direction: 'bullish' | 'bearish' | 'neutral'
    confidence: number
    detail?: string
    scores?: Record<string, unknown>
    keypoint_allowed?: boolean
    keypoint_reject_reason?: string
    buy_point_category?: string
  }>
  fusion_type?: string
  fusion_reason?: string
  wave_position?: string
  /** 操作建议（由卡片统一推导） */
  action_type?: string       // 交易动作，或复盘分层后的'观察'/'技术信号'/'待确认'
  action_signal?: string     // '强势买入·缩量回踩(85)' / '偏多等确认' / ...
  action_priority?: string   // '高'/'中'/'低'
  action_reason?: string     // 操作理由文字
  decision_status?: 'executable' | 'candidate' | 'signal_only' | 'blocked'
  data_quality?: 'ready' | 'sector_unavailable'
  attention_tier?: 'focus' | 'watch' | 'ordinary'
  attention_reason?: string
  momentum_rank?: number
  momentum_total?: number | null
  momentum_source?: '行业' | '概念' | string
  momentum_direction?: string
  quality_score?: number | null
  quality_basis?: string
  buy_point_category?: 'breakout' | 'continuation' | 'range_support' | 'reversal' | 'panic' | 'unknown'
  buy_point_category_label?: string
  structural_compatible?: boolean
  structural_compatibility_reason?: string
  market_compatible?: boolean | null
  market_compatibility_reason?: string
  trigger_condition?: string
  action_when_triggered?: string
  invalidation_condition?: string
  stop_condition?: string
  valid_for?: string
  plan_readiness?: 'ready' | 'needs_stop'
}

/** 止损预警API返回类型 */
export interface StopLossData {
  triggered?: StopLossItem[]
}

export interface StopLossItem {
  name: string
  code: string
  current_price: number
  stop_loss: number
  loss_pct: number
  reason: string
}

/** 工作台计划API返回类型 */
export interface WorkbenchPlan {
  plan?: {
    buy?: PlanItem[]
    sell?: PlanItem[]
    watch?: PlanItem[]
  }
}

export interface PlanItem {
  stock?: string
  sector?: string
  condition?: string
  action_when_triggered?: string
  invalidation_condition?: string
  stop_condition?: string
  valid_for?: string
  plan_readiness?: 'ready' | 'needs_stop'
  qty?: string
  status?: 'executed' | 'triggered' | 'not_triggered' | 'pending'
  focus?: string
  stop_loss?: number
  stop_loss_pct?: number
  alert?: AlertItem | null
}

export interface AlertItem {
  type: 'price' | 'deviation' | 'time'
  stock?: string
  condition: string
  enabled: boolean
}

/** 外围关联API返回类型 */
export interface ExternalMappingData {
  asia_indices?: ExternalIndex[]
  us_indices?: ExternalIndex[]
  categories?: ExternalCategory[]
  updated?: string
  source_url?: string
  source?: string
}

export interface ExternalIndex {
  name: string
  flag?: string
  market_hours?: string
}

export interface ExternalCategory {
  name: string
  stocks?: ExternalStock[]
}

export interface ExternalStock {
  code: string
  name: string
  impact?: string
  sectors?: string
  suppliers?: string
  potential?: string
  counterparts?: string
}

/** 行业板块列表 */
export interface IndustryBoardItem {
  板块?: string
  名称?: string
  涨跌幅?: number
}

/** 行业映射 */
export type IndustryMap = Record<string, { ths_industry?: string }>

/** 复盘数据结构 */
export interface MarketStrategy {
  environment: 'strong' | 'neutral' | 'weak' | 'unknown'
  environment_label: string
  risk_phase: 'main_decline' | 'risk_rising' | 'valley_recovery' | 'normal'
  risk_label: string
  wave_phase: string
  wave_label: string
  position_mode: 'defensive' | 'reduce' | 'increase_on_signal' | 'follow_signals'
  position_action: string
  current_position_pct: number | null
  planned_exit_pct: number | null
  position_after_exits_pct: number | null
  executable_buy_count: number
  allowed_buy_points: string[]
  avoid_buy_points: string[]
  holding_style: string
  exit_style: string
  summary: string
  basis: string[]
}

export interface ReviewData {
  previous_trading_date?: string
  date?: string
  data_status?: ReviewDataStatus
  /** @deprecated v3 客户端使用 data_status */
  data_dates?: { requested?: string; index?: string; stocks?: string; sectors?: string }
  /** @deprecated v3 客户端使用 data_status */
  data_freshness?: { index?: 'current' | 'stale' | 'unknown'; stocks?: 'current' | 'stale' | 'unknown'; sectors?: 'current' | 'stale' | 'unknown' }
  response_meta?: { source: 'cache' | 'archive' | 'live'; computed_live: boolean; contract_version: number; deprecated_fields?: string[] }
  cache_generated_at?: string
  refresh_status?: import('./api').ReviewRefreshStatus
  market?: {
    price?: number | string
    change?: number
    score?: number
    position?: string
    position_pct?: string
    strategy?: string
    build_per_stock_pct?: string
    pk_score?: number
    vl_score?: number
    bias20?: number
    bias20_chg_3d?: number
    ma20?: number
    ma60?: number
    structure?: string
    market_regime?: 'strong' | 'neutral' | 'weak' | 'unknown'
    data_date?: string
  }
  mainline?: {
    ranking_status?: 'confirmed' | 'estimated' | 'partial' | 'stale'
    ranking_date?: string
    base_date?: string
    estimate_coverage?: number | null
    estimate_coverage_detail?: EstimateCoverageDetail
    calibration?: MainlineCalibration | null
    lines?: LineItem[]
    secondary?: LineItem[]
    persistence?: { name: string; days: number; status: string }[]
    all_ranked?: LineItem[]
    l1_shadow?: {
      model_type?: string
      experimental?: boolean
      as_of_date?: string
      data_status?: 'experimental' | 'partial' | 'error'
      calibration_status?: string
      source?: string
      input_coverage?: Record<string, number | string | null | undefined>
      quality_gates?: Record<string, boolean | null | undefined>
      rankings?: Array<{
        name: string
        momentum_stock_count?: number
        constituent_count?: number
        coverage?: number
        momentum_score?: number
        status?: string
        score_status?: string
        rotation_state?: string
        consecutive_days?: number
        new_high_count?: number | null
        new_high_overlap?: number | null
        top_stocks?: string[]
      }>
      error?: string
      error_type?: string
    }
    concept_mainline?: {
      ranking_status?: 'confirmed' | 'estimated' | 'partial' | 'stale'
      ranking_date?: string
      base_date?: string
      estimate_coverage?: number | null
      estimate_coverage_detail?: EstimateCoverageDetail
      coverage?: number | null
      coverage_detail?: EstimateCoverageDetail
      lines?: LineItem[]
      secondary?: LineItem[]
      persistence?: { name: string; days: number; status: string }[]
      all_ranked?: LineItem[]
    }
  }
  /** 关注行业/关注概念（按用户，从 all_ranked 匹配；matched=false 表示主线暂无数据） */
  watched_sectors?: {
    industries?: Array<Partial<LineItem> & { name: string; matched?: boolean }>
    concepts?: Array<Partial<LineItem> & { name: string; matched?: boolean }>
  }
  holdings_review?: BuySignalItem[]
  holdings_risk_exposure?: HoldingsRiskExposure
  holdings?: BuySignalItem[]
  buy_signals_review?: BuySignalItem[]
  direction_order?: string[]
  opportunity_map?: Record<string, string>  // sector/concept → opportunity type
  trading_plan?: {
    overall_strategy?: string
    position_level?: string
    build_per_stock_pct?: string
    main_lines?: string[]
    position_detail?: string
    market_strategy?: MarketStrategy
    holdings_action?: Array<{
      stock: string
      action: string
      reason: string
      priority: string
      trigger_condition?: string
      action_when_triggered?: string
      invalidation_condition?: string
      stop_condition?: string
      valid_for?: string
      plan_readiness?: 'ready' | 'needs_stop'
    }>
    buy_priority?: (BuySignalItem & { is_main?: boolean; sector?: string; opportunity?: string })[]
    buy_summary?: {
      total: number
      focus: number
      watch: number
      ordinary: number
      market_regime?: 'strong' | 'neutral' | 'weak' | 'unknown'
      conclusion: string
      ranking_rule: string
    }
    risk_items?: string[]
  }
  charts?: {
    index_chart?: string
    fund_flow?: string
  }
}

export interface HoldingsRiskExposureItem {
  code: string
  name: string
  direction: string
  position_pct: number | null
  cost_price: number | null
  current_price: number | null
  stop_loss: number | null
  stop_loss_source?: 'manual' | 'system' | 'unknown'
  stop_loss_warning?: string
  downside_to_stop_pct: number | null
  portfolio_risk_pct: number | null
  unrealized_pnl_pct: number | null
  stop_status: 'covered' | 'breached' | 'unassessable' | 'missing'
}

export interface HoldingsRiskExposure {
  status: 'confirmed' | 'partial'
  basis: string
  total_position_pct: number
  cash_pct: number | null
  stop_covered_position_pct: number
  breached_position_pct: number
  unassessable_position_pct: number
  uncovered_position_pct: number
  portfolio_downside_to_stops_pct: number
  largest_position: { code: string; name: string; position_pct: number } | null
  direction_concentration: Array<{ name: string; position_pct: number }>
  breached_stop_codes: string[]
  stop_warnings: Array<{ code: string; name: string; message: string }>
  missing: string[]
  items: HoldingsRiskExposureItem[]
}

export type ReviewDataState = 'confirmed' | 'estimated' | 'partial' | 'stale' | 'unknown'

export interface EstimateCoverageDetail {
  covered?: number | null
  expected?: number | null
  ready?: boolean | null
  missing?: string[]
}

export interface ReviewDataStatusItem {
  status: ReviewDataState
  date?: string
  confirmed_date?: string
  base_date?: string
  coverage?: number | null
  coverage_detail?: EstimateCoverageDetail
}

export interface ReviewDataStatus {
  requested_date?: string
  overall?: 'ready' | 'partial' | 'stale'
  index?: ReviewDataStatusItem
  stocks?: ReviewDataStatusItem
  industry?: ReviewDataStatusItem
  concept?: ReviewDataStatusItem
}

/** 主线/板块行项目 */
export interface LineItem {
  name: string
  chg_20d: number
  chg_1d?: number
  stage?: string
  vl_score?: number
  volume_ratio?: number
  opportunity?: string
  is_mainline?: boolean
  is_secondary?: boolean
  estimate_applied?: boolean
}

export interface MainlineCalibration {
  status: 'pending' | 'completed'
  estimated_top10?: string[]
  confirmed_top10?: string[]
  estimate_coverage?: number
  entered?: string[]
  exited?: string[]
  top5_overlap?: number
  top10_overlap?: number
}
