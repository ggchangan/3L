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
}

/** 板块监测API返回类型 */
export interface SectorData {
  today_top5?: SectorItem[]
  chg5d_top5?: SectorItem[]
}

export interface SectorItem {
  name: string
  chg?: number
  chg5d?: number
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

/** 买点信号API返回类型 */
export interface BuySignalsData {
  signals?: BuySignalItem[]
  scan_time?: string
  stocks_scanned?: number
}

export interface BuySignalItem {
  code: string
  name: string
  signal: 'buy' | 'sell' | 'hold'
  stage: string
  structure: string
  trading_system?: '3l' | 'trend'
  buy_point?: string
  stop_loss?: number
  stop_loss_pct?: number
  profit_model1?: boolean
  trend_stock?: boolean
  trend_bias?: number
  direction?: string
  change?: number
  price?: number
  vol_analysis?: string
  sector?: string
  sector_chg?: number
  mainline_level?: string
  trading_reason?: string
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
  qty?: string
  status?: 'executed' | 'triggered' | 'not_triggered' | 'pending'
  focus?: string
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
