import type {
  VolumeData,
  SectorData,
  LeadersData,
  MarketLeadersData,
  BuySignalsData,
  StopLossData,
  WorkbenchPlan,
  ExternalMappingData,
  IndustryBoardItem,
  IndustryMap,
  ReviewData,
} from './types'

const BASE = '' // 同源请求，无前缀

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${url}`)
  return res.json()
}

export function fetchVolume(): Promise<VolumeData> {
  return fetchJson<VolumeData>('/api/monitor/volume')
}

export function fetchSectors(): Promise<SectorData> {
  return fetchJson<SectorData>('/api/monitor/sectors')
}

export function fetchIndustryLeaders(): Promise<LeadersData> {
  return fetchJson<LeadersData>('/api/monitor/leaders')
}

export function fetchMarketLeaders(): Promise<MarketLeadersData> {
  return fetchJson<MarketLeadersData>('/api/monitor/market-leaders')
}

export function fetchBuySignals(): Promise<BuySignalsData> {
  return fetchJson<BuySignalsData>('/api/monitor/buy-signals')
}

export function fetchStopLoss(): Promise<StopLossData> {
  return fetchJson<StopLossData>('/api/monitor/stop-loss')
}

export function fetchWorkbenchPlan(date: string): Promise<WorkbenchPlan> {
  return fetchJson<WorkbenchPlan>(`/api/workbench/get?date=${date}`)
}

export function fetchExternalMapping(): Promise<ExternalMappingData> {
  return fetchJson<ExternalMappingData>('/api/external-mapping')
}

/** 报警监听接口 */
export interface StoredAlarm {
  id: string
  stock: string
  stock_code: string
  type: 'price' | 'deviation' | 'time'
  enabled: boolean
  stop_loss?: number
  stop_loss_pct?: number
  condition: string
  created: string
  status: string
  expires_days: number
}

export interface AlarmListData {
  alarms: StoredAlarm[]
  count: number
}

export function fetchActiveAlarms(): Promise<AlarmListData> {
  return fetchJson<AlarmListData>('/api/alarms/list')
}

export function fetchIndustryBoards(): Promise<{ data: IndustryBoardItem[] }> {
  return fetchJson<{ data: IndustryBoardItem[] }>('/api/industry-boards')
}

export function fetchIndustryMap(): Promise<IndustryMap> {
  return fetchJson<IndustryMap>('/api/industry-map')
}

export function fetchStockSummary(code: string): Promise<Record<string, unknown>> {
  return fetchJson(`/api/stock-summary?code=${code}`)
}

/** 复盘相关 API */
export function fetchReviewToday(): Promise<ReviewData> {
  return fetchJson<ReviewData>('/api/review/today')
}

export function fetchReviewDates(): Promise<{ dates: string[] }> {
  return fetchJson('/api/review/dates')
}

export function fetchReviewByDate(date: string): Promise<ReviewData> {
  return fetchJson<ReviewData>(`/api/review/${date}`)
}

export function fetchMarket(): Promise<Record<string, unknown>> {
  return fetchJson('/api/market')
}

/** 格式化成交额 */
export function fmtAmountYuan(v?: number): string {
  if (!v) return '0'
  return (v / 100000000).toFixed(1) + '亿'
}

/** 格式化成交量 */
export function fmtVol(v?: number): string {
  if (!v) return '0'
  if (v >= 100000000) return (v / 100000000).toFixed(1) + '亿'
  if (v >= 10000) return (v / 10000).toFixed(0) + '万'
  return v.toLocaleString()
}

/** 获取昨日日期 YYYY-MM-DD */
export function getYesterdayStr(): string {
  const d = new Date()
  d.setDate(d.getDate() - 1)
  return d.toISOString().slice(0, 10)
}
