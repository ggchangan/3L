"""StockCardService — 统一个股卡片数据服务
输入股票代码+上下文，输出完整的卡片数据，不再重复组装逻辑

所有I/O通过 backend.core.data_layer，不直接读文件。

用法:
    from backend.services.stock_card_service import get_stock_card
    card = get_stock_card(code='002916', date_str='20260525',
                          market_position='波中', main_lines=[])
"""

import os, sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.config import MANUAL_TREND_PATH as _MANUAL_TREND_PATH, DATA_DIR
from backend.core.data_layer import (
    get_stock_klines,
    get_industry_map,
)

# 统一名字源：all_a_stocks.json — 5317只全量A股 {code: name}
_ALL_A_STOCKS = {}
_aas_path = os.path.join(DATA_DIR, 'all_a_stocks.json')
if os.path.isfile(_aas_path):
    try:
        import json
        with open(_aas_path) as _f:
            _ALL_A_STOCKS = json.load(_f)
    except Exception:
        pass
from backend.core.ema_utils import (
    ema_list,
    get_ema_arrangement,
    get_structure,
    get_stage,
)
from backend.core.buy_point_detection import (
    detect_buy_point,
    calc_stop_loss,
)
from backend.core.trend_trading import (
    detect_trend_buy,
    decide_system_with_detail,
)
from backend.core.signal_detector.fusion import fusion_judge
from backend.core.signal_detector.sell_point_detection import detect_sell_point
from backend.core.structure_wave import judge_structure_wave

# 板块K线缓存（模块级，只加载一次）
_SECTOR_DAILY = None

def _load_sector_daily():
    global _SECTOR_DAILY
    if _SECTOR_DAILY is not None:
        return _SECTOR_DAILY
    _sdp = os.path.join(DATA_DIR, 'sector_daily.json')
    if os.path.isfile(_sdp):
        try:
            import json
            with open(_sdp) as _f:
                _SECTOR_DAILY = json.load(_f)
        except Exception:
            _SECTOR_DAILY = {}
    else:
        _SECTOR_DAILY = {}
    return _SECTOR_DAILY

def _calc_sector_chg_5d(sector):
    """计算板块5日涨跌幅（通过 data_source 抽象层获取K线）"""
    try:
        from backend.core.data_layer import get_sector_klines
        klines = get_sector_klines(sector, 'industry')
    except Exception:
        klines = []
    if len(klines) < 6:
        return None
    close_now = klines[-1]['close']
    close_5ago = klines[-6]['close']
    if close_5ago <= 0:
        return None
    return round((close_now - close_5ago) / close_5ago * 100, 2)


# ── 手动趋势股（不缓存，文件很小直接读）──
MANUAL_TREND_PATH = _MANUAL_TREND_PATH


def _load_manual_trend():
    """加载手动趋势股列表（每次读文件，不缓存）"""
    try:
        import json
        with open(MANUAL_TREND_PATH) as f:
            return set(json.load(f))
    except Exception:
        return set()


# ═══════════════════════════════════════════
# 内部函数
# ═══════════════════════════════════════════

def _find_idx(klines, date_str):
    """在K线列表中找指定日期的索引"""
    date_clean = date_str.replace('-', '')
    for i, k in enumerate(klines):
        if str(k.get('date', '')).replace('-', '') == date_clean:
            return i
    return len(klines) - 1


def _analyze_structure(klines, idx):
    """分析结构和阶段"""
    if idx < 0 or idx >= len(klines):
        return {'structure': '--', 'stage': '--', 'ema': '--'}

    closes = [k['close'] for k in klines[:idx + 1]]
    highs = [k['high'] for k in klines[:idx + 1]]
    lows = [k['low'] for k in klines[:idx + 1]]
    volumes = [k['volume'] for k in klines[:idx + 1]]

    structure = get_structure(closes)
    stage = get_stage(closes, structure=structure, highs=highs,
                      lows=lows, volumes=volumes)
    ema = get_ema_arrangement(closes)

    return {
        'structure': structure or '--',
        'stage': stage or '--',
        'ema': ema or '--',
    }


def _decide_trading_system(code):
    """判定交易系统：'trend' 或 '3l'"""
    manual = _load_manual_trend()
    return 'trend' if code in manual else '3l'


def _calc_sector_chg(code):
    """计算板块今日涨幅（暂不可行，外部需要实时行情）"""
    return None


def _calc_stop_loss(klines, idx, buy_type=None, entry_idx=None):
    """计算止损价和百分比 — 按买点类型"""
    try:
        if idx < 10 or len(klines) <= idx:
            return None, None
        sl, sl_pct = calc_stop_loss(klines, idx, buy_type=buy_type, entry_idx=entry_idx)
        return float(sl) if sl else None, float(sl_pct) if sl_pct else None
    except Exception:
        return None, None


def _get_mainline_level(sector, main_line_names, sub_main_names, concept_names=None, concept_main=None, concept_sub=None):
    """判断主线等级：行业主线优先，概念主线补充"""
    if not sector:
        return ''
    # 行业主线判定
    if sector in main_line_names:
        return '主线'
    elif sector in sub_main_names:
        return '次级主线'
    # 概念主线补充判定
    if concept_names and concept_main:
        for cn in concept_names:
            if cn in concept_main:
                return '主线'
    if concept_names and concept_sub:
        for cn in concept_names:
            if cn in concept_sub:
                return '次级主线'
    return '非主线'


def _build_conclusion(card):
    """生成结论文字"""
    s = card['signal']
    ts = card['trading_system']
    stage = card.get('stage', '')
    structure = card.get('structure', '')
    buy_point = card.get('buy_point', '')
    stop_loss = card.get('stop_loss')
    stop_loss_pct = card.get('stop_loss_pct')
    fusion_type = card.get('fusion_type', '')
    fusion_reason = card.get('fusion_reason', '')
    triggered = card.get('triggered_signals', [])

    sl_text = ''
    if stop_loss and stop_loss_pct:
        sl_text = f'，建议止损{stop_loss:.2f}（约{stop_loss_pct:.1f}%）'

    if ts == 'trend':
        bias = card.get('trend_bias')
        if bias is not None and bias != '':
            bias_f = float(bias)
            if s == 'buy':
                return f'BIAS5={bias_f:.2f}%，乖离率买入区{sl_text}'
            elif bias_f < 0:
                return f'BIAS5={bias_f:.2f}%，价格在EMA5下方，乖离率买入区，属于趋势交易乖离率买点'
            elif bias_f <= 2:
                return f'BIAS5={bias_f:.2f}%，价格靠近EMA5，乖离率买入区，可考虑逢低吸纳'
            elif bias_f <= 8:
                return f'BIAS5={bias_f:.2f}%，价格在EMA5上方，持有区，趋势健康继续持有'
            else:
                return f'⚠️ BIAS5={bias_f:.2f}%，价格远离EMA5，警戒区，关注回调风险'
        return f'趋势交易，{stage}阶段，{structure}'

    # 融合判定优先
    if fusion_type == 'strong_buy' and s == 'buy':
        # 列举触发的信号
        sig_str = '，'.join([f'{t["name"]}({t["confidence"]:.0f})' for t in triggered[:3]])
        return f'触发{buy_point}，{sig_str}信号确认，可执行买入计划{sl_text}'

    if fusion_type == 'signal_buy' and s == 'buy':
        sig_str = '，'.join([f'{t["name"]}({t["confidence"]:.0f})' for t in triggered[:2]])
        return f'{sig_str}，{stage}阶段，关键点位看多，倾向买入{sl_text}'

    if fusion_type == 'signal_sell' and s == 'sell':
        sig_str = '，'.join([f'{t["name"]}({t["confidence"]:.0f})' for t in triggered[:2]])
        return f'{sig_str}，关键点偏空，建议卖出避险'

    if fusion_type == 'conflict_bearish':
        return f'结构{structure}·{stage}偏多，但出现向下信号，需警惕'

    if fusion_type == 'conflict_bullish':
        return f'结构偏空但出现看多信号，等确认再入场'

    # 回退到原有逻辑
    if s == 'buy':
        return f'触发{buy_point}，{stage}阶段确认，可执行买入计划{sl_text}'

    # hold/sell — 参考 review_analysis 的结论生成逻辑
    if stage == '缩量整理':
        return '量能卖压枯竭，价在EMA10之上，中继蓄力形态，可持股等待放量突破'
    elif stage == '上行':
        return '斜率正常，EMA10持续向上，上行趋势健康，继续持有不动'
    elif stage == '加速':
        return 'EMA10斜率加速变陡，拉升阶段，关注放量滞涨等左侧止盈信号'
    elif stage == '放量滞涨':
        return '⚠️ 放量+价不涨，高位换手密集，左侧预警信号，建议减仓避险'
    elif stage == '缩量滞涨':
        return '⚠️ 缩量横盘不创新高，需求逐步衰竭，建议减仓观望'
    elif stage == '滞涨':
        return 'EMA10走平涨不动，警惕回调，考虑减仓'
    elif stage == '转弱':
        return 'EMA10已拐头向下，趋势转弱，关注关键支撑位是否破位'
    elif stage == '区间底部':
        return '价格在支撑位附近，区间底部企稳，可考虑加仓博反弹'
    elif stage == '区间顶部':
        return '价格接近压力位，区间顶部受阻，注意减仓回避'
    elif stage == '区间中段':
        return '区间中部无明确方向，等待价格靠近支撑或压力再做决定'
    else:
        return f'阶段{stage}，{structure}'


def _build_tags(card):
    """生成标签列表"""
    tags = []
    if card.get('profit_model1'):
        tags.append('🏆 盈利1')
    if card.get('trend_stock'):
        tags.append('📈 趋势股')
    return tags


# ═══════════════════════════════════════════
# 操作建议推导（与 StockCardData 合约一致）
# ═══════════════════════════════════════════

# 以下 4 个函数严格对应旧 _make_item_action 逻辑（无 fusion 优先）。
# 旧的 _make_item_action 只根据 signal → stage 推导，fusion_type 未参与。

def _calc_action_type(signal, stage, fusion_type):
    """计算操作类型 — 严格对应旧 _make_item_action 逻辑"""
    if signal == 'sell':
        return '卖出'
    if signal == 'buy':
        return '买入'
    _stage_action = {
        '加速': '持有',
        '缩量整理': '持有',
        '上行': '持有',
        '滞涨': '减仓',
        '转弱': '换股',
        '区间底部': '加仓',
        '区间顶部': '减仓',
        '区间中段': '持有',
    }
    return _stage_action.get(stage, '持有')


def _calc_action_signal(signal, stage, fusion_type, triggered_signals):
    """计算操作子标签 — 严格对应旧 _make_item_action 逻辑"""
    if signal == 'sell':
        return ''
    if signal == 'buy':
        return '买点'  # 旧逻辑 buy 信号返回 buy_point or '买点'
    _stage_signal = {
        '加速': '关注止盈',
        '缩量整理': '可加仓',
        '上行': '',
        '滞涨': '警惕滞涨',
        '转弱': '关注转弱',
        '区间底部': '支撑位',
        '区间顶部': '压力位',
        '区间中段': '',
    }
    return _stage_signal.get(stage, '')


def _calc_action_priority(signal, stage, fusion_type):
    """计算优先级 — 严格对应旧 _make_item_action 逻辑"""
    if signal in ('buy', 'sell'):
        return '高'
    _stage_pri = {
        '加速': '中',
        '缩量整理': '中',
        '上行': '低',
        '滞涨': '高',
        '转弱': '高',
        '区间底部': '中',
        '区间顶部': '高',
        '区间中段': '低',
    }
    return _stage_pri.get(stage, '中')


def _calc_action_reason(signal, structure, stage, fusion_reason,
                        triggered_signals, buy_point):
    """计算操作理由 — 严格对应旧 _make_item_action 逻辑"""
    if signal == 'sell':
        return f'{structure}·{stage}'
    if signal == 'buy':
        return f'{structure}·{stage}'
    _stage_reason = {
        '加速': f'{structure}·{stage}，关注放量滞涨/加速变缓',
        '缩量整理': f'{structure}·{stage}，供应枯竭等待放量',
        '上行': f'{structure}·{stage}，趋势健康',
        '滞涨': f'{structure}·{stage}，EMA10走平',
        '转弱': f'{structure}·{stage}，EMA10拐头向下',
        '区间底部': f'{structure}·{stage}，区底企稳',
        '区间顶部': f'{structure}·{stage}，区顶受阻',
        '区间中段': f'{structure}·{stage}，方向未明',
    }
    return _stage_reason.get(stage, f'{structure}·{stage}')


# ═══════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════

def get_stock_card(code, date_str, market_position='波中',
                   main_lines=None, direction=None, klines=None):
    """
    获取个股卡片数据

    Args:
        code: 6位股票代码
        date_str: 日期 'YYYYMMDD' 或 'YYYY-MM-DD'
        market_position: 大盘位置
        main_lines: 主线列表 [{'name': ...}]
        direction: 方向组（可选）
        klines: 可选，预加载的K线数据（如盘中实时数据），
                不传则从 data_layer 自动加载

    Returns:
        dict: 完整的卡片数据
    """
    if main_lines is None:
        main_lines = []

    # 统一 main_lines 格式：dict → 内部 dict，list → dict
    if isinstance(main_lines, list):
        _mainlines = {'lines': [{'name': m} for m in main_lines if isinstance(m, str)],
                      'secondary': []}
    else:
        _mainlines = main_lines
    main_line_names = [l['name'] for l in _mainlines.get('lines', [])]
    sub_main_names = [l['name'] for l in _mainlines.get('secondary', [])]

    # 概念主线数据
    _cm = _mainlines.get('concept_mainline', {})
    concept_main_names = [l['name'] for l in _cm.get('lines', [])]
    concept_sub_names = [l['name'] for l in _cm.get('secondary', [])]
    # 个股概念名称（for 概念主线补充判定）
    _stock_concept_names = []
    try:
        from backend.core.data_layer import get_stock_concept_map
        _scm = get_stock_concept_map()
        _sinfo = _scm.get(code, {})
        _stock_concept_names = _sinfo.get('concept_names', []) if isinstance(_sinfo, dict) else []
    except:
        pass

    # 1. 获取基础信息
    industry_map = get_industry_map()
    stock_info = industry_map.get(code, {})
    if isinstance(stock_info, dict):
        sector = stock_info.get('ths_industry', '') or direction or ''
    else:
        sector = direction or ''

    # 名字统一从 all_a_stocks.json 取
    name = _ALL_A_STOCKS.get(code, code)

    # 2. 获取K线：优先外部传入，否则从 data_layer 加载
    if klines is not None:
        pass  # 用传入的
    else:
        klines = get_stock_klines(code, direction)
    if not klines or len(klines) < 30:
        return _empty_card(code, name, sector, direction, '数据不足')

    idx = _find_idx(klines, date_str)
    if idx < 10:
        idx = len(klines) - 1

    close = klines[idx]['close']
    # 涨跌幅：拿最近2根算
    change = 0.0
    if idx > 0:
        prev_close = klines[idx - 1]['close']
        if prev_close > 0:
            change = round((close - prev_close) / prev_close * 100, 2)

    # 3. 结构分析
    struct_info = _analyze_structure(klines, idx)

    # 通用 EMA 数值、偏离率、量比
    closes_all = [k['close'] for k in klines[:idx + 1]]
    ema5_val = float(ema_list(closes_all, 5)[-1]) if len(closes_all) >= 5 and ema_list(closes_all, 5)[-1] else None
    ema10_val = float(ema_list(closes_all, 10)[-1]) if len(closes_all) >= 10 and ema_list(closes_all, 10)[-1] else None
    ema20_val = float(ema_list(closes_all, 20)[-1]) if len(closes_all) >= 20 and ema_list(closes_all, 20)[-1] else None
    ema30_val = float(ema_list(closes_all, 30)[-1]) if len(closes_all) >= 30 and ema_list(closes_all, 30)[-1] else None
    deviation_pct = round((close - ema5_val) / ema5_val * 100, 2) if ema5_val and ema5_val > 0 else 0
    vol_ratio = 0
    if idx >= 5:
        vols = [k.get('volume', k.get('vol', 0)) for k in klines[idx-4:idx+1]]
        vma5 = sum(vols) / 5 if all(v > 0 for v in vols) else 0
        cur_vol = klines[idx].get('volume', klines[idx].get('vol', 0))
        vol_ratio = round(cur_vol / vma5, 2) if vma5 > 0 else 0

    # 4. 交易系统判定
    trading_system = _decide_trading_system(code)
    sys_detail = {'system': trading_system,
                  'reason': '手动指定为趋势交易' if trading_system == 'trend' else '默认3L交易'}

    # 5. 买点判定（互斥：趋势/3L）
    buy_point = ''
    trend_buy_type = ''
    trend_bias = ''
    signal = 'hold'
    signal_text = ''
    score = 0
    vol_analysis = '--'
    profit_model1 = False
    trend_stock = False
    flags = ''
    stop_loss = None
    stop_loss_pct = None
    _3l_detail = {}

    date_clean = date_str.replace('-', '')

    if trading_system == 'trend':
        trend_stock = True
        tb = detect_trend_buy(code, date_clean,
                              {sector: {code: klines}}, main_line_names)
        if tb:
            signal = 'buy'
            signal_text = '趋势买入'
            trend_buy_type = tb.get('buy_type', '')
            trend_bias = tb.get('bias5', '')
            buy_point = trend_buy_type
            score = 5
        else:
            signal = 'hold'
            # 即使没有买点也展示乖离率
            from backend.core.trend_trading import check_trend_type
            t = check_trend_type(klines, idx)
            if t.get('trend_type'):
                trend_bias = t.get('bias5', '')
    else:
        # 3L 买点检测（需要全量数据）
        all_stocks = {}
        try:
            from backend.core.data_layer import get_all_stocks
            all_stocks = get_all_stocks()
        except Exception:
            all_stocks = {sector: {code: klines}}

        # 外部传了实时K线时，覆盖 all_stocks 中对应股票的K线（含预估成交量）
        if klines is not None and all_stocks:
            for sec in list(all_stocks.keys()):
                if code in all_stocks[sec]:
                    all_stocks[sec][code] = klines
                    break

        bt = detect_buy_point(code, date_clean, all_stocks,
                              market_position=market_position,
                              main_lines=main_line_names)
        if bt:
            signal = 'buy'
            buy_point = bt.get('buy_type', '')
            signal_text = bt.get('detail', {}).get('reason', '')
            score = bt.get('score', 0)
            vol_analysis_text = ''
            vr = bt.get('vol_ratio', 0)
            if vr < 0.7:
                vol_analysis_text = f'缩量{vr:.0%}'
            elif vr > 1.5:
                vol_analysis_text = f'放量{vr:.0%}'
            else:
                vol_analysis_text = f'量能正常{vr:.0%}'
            vol_analysis = vol_analysis_text
            profit_model1 = bt.get('profit_model1', False) or bt.get('detail', {}).get('profit_model1', False)
            flags = bt.get('flags', '')
            _3l_detail = bt.get('detail', {})

    # 5b. 卖出判定（当无买点信号时，基于结构+阶段判定）
    if signal == 'hold':
        struct = struct_info.get('structure', '')
        stage = struct_info.get('stage', '')
        if struct == '下降趋势' or stage in ('转弱', '滞涨', '放量滞涨', '缩量滞涨', '下行', '加速跌'):
            signal = 'sell'
            signal_text = signal_text or f'{stage}·建议减仓'

    # 5c. 关键点×关键信号融合判定
    try:
        f_result = fusion_judge(
            klines, idx, main_line_names, sector,
            existing_signal=signal, existing_buy_point=buy_point,
            structure=struct_info.get('structure', ''),
            stage=struct_info.get('stage', ''),
            ema_arrangement=struct_info.get('ema', ''),
            bias5=deviation_pct,
        )
        triggered_signals = f_result.get('triggered_signals', [])
        fusion_type = f_result.get('fusion_type', '')
        fusion_reason = f_result.get('reason', '')

        # 融合判定覆盖规则：
        # - 已有买点+融合确认→增强置信度
        # - 无买点但融合出buy→采用
        # - 无卖出但融合出sell→采用
        if fusion_type in ('strong_buy', 'signal_buy'):
            if signal == 'hold':
                signal = 'buy'
                buy_point = '信号确认'
                signal_text = f_result.get('signal_text', '')
                score = min(100, f_result['confidence'])
            elif signal == 'buy':
                score = max(score, f_result['confidence'])
        elif fusion_type == 'signal_sell' and signal != 'sell':
            signal = 'sell'
            signal_text = f_result.get('signal_text', '')
            score = f_result['confidence']
    except Exception:
        triggered_signals = []
        fusion_type = ''
        fusion_reason = ''

    # 5d. 独立卖点引擎（补充融合判定未覆盖的场景）
    if signal != 'sell':
        try:
            sp = detect_sell_point(klines, idx,
                                   structure=struct_info.get('structure', ''),
                                   stage=struct_info.get('stage', ''),
                                   bias5=deviation_pct)
            if sp.get('triggered'):
                sell_cf = sp.get('confidence', 0)
                if sell_cf > score:  # 卖点置信度更高才覆盖
                    signal = 'sell'
                    signal_text = sp.get('sell_type', '')
                    buy_point = ''
                    score = sell_cf
                    # 追加一个卖点信号到triggered_signals
                    triggered_signals.append({
                        'key': 'sell_point_detector',
                        'name': sp.get('sell_type', '卖出'),
                        'direction': 'bearish',
                        'confidence': sell_cf,
                        'detail': sp.get('reason', ''),
                        'scores': {},
                    })
        except Exception:
            pass

    # 5e. 个股波峰波谷位置（辅助字段，波谷可用于买点确认）
    wave_position = ''
    try:
        wr = judge_structure_wave(klines, structure=struct_info.get('structure', ''))
        wave_position = wr.get('position', '')
        wave_stage = wr.get('stage', '')
    except Exception:
        wave_position = ''
        wave_stage = ''

    # 6. 止损（按买点类型）
    sl_result = _calc_stop_loss(klines, idx, buy_type=buy_point if buy_point else None, entry_idx=idx if buy_point else None)
    if sl_result and sl_result[0]:
        stop_loss, stop_loss_pct = sl_result
    elif signal == 'buy' and close > 0:
        # 有买点但算不出支撑位，用EMA20兜底
        ema20_sl = round(ema20_val * 0.97, 2) if ema20_val and ema20_val > 0 else None
        if ema20_sl:
            stop_loss = ema20_sl
            stop_loss_pct = round((close - ema20_sl) / close * 100, 2)

    # 7. 主线定位（行业+概念双检）
    mainline_level = _get_mainline_level(sector, main_line_names, sub_main_names,
                                         concept_names=_stock_concept_names,
                                         concept_main=concept_main_names,
                                         concept_sub=concept_sub_names)

    # 7b. 板块对比：个股5日涨幅 vs 板块5日涨幅
    stock_chg_5d = None
    vs_sector_5d = None
    if len(closes_all) >= 6 and closes_all[-6] > 0:
        stock_chg_5d = round((closes_all[-1] - closes_all[-6]) / closes_all[-6] * 100, 2)
        sector_chg_5d = _calc_sector_chg_5d(sector)
        if sector_chg_5d is not None:
            vs_sector_5d = round(stock_chg_5d - sector_chg_5d, 2)

    # 7c. 操作建议（由卡片统一推导，外部不重复计算）
    action_type = _calc_action_type(signal, struct_info.get('stage', '--'), fusion_type)
    action_signal = _calc_action_signal(signal, struct_info.get('stage', '--'),
                                         fusion_type, triggered_signals)
    action_priority = _calc_action_priority(signal, struct_info.get('stage', '--'), fusion_type)
    action_reason = _calc_action_reason(signal, struct_info.get('structure', '--'),
                                         struct_info.get('stage', '--'),
                                         fusion_reason, triggered_signals, buy_point)

    # 8. 构建卡片
    card = {
        'code': code,
        'name': name,
        'sector': sector,
        'direction': direction or '',
        'price': close,
        'change': change,
        'date': date_clean,
        'structure': struct_info.get('structure', '--'),
        'stage': struct_info.get('stage', '--'),
        'ema': struct_info.get('ema', '--'),
        'ema5': ema5_val,
        'ema10': ema10_val,
        'ema20': ema20_val,
        'ema30': ema30_val,
        'deviation_pct': deviation_pct,
        'vol_ratio': vol_ratio,
        'vol_analysis': vol_analysis,
        'signal': signal,
        'signal_text': signal_text,
        'buy_point': buy_point,
        'profit_model1': profit_model1,
        'trend_stock': trend_stock,
        'trading_system': trading_system,
        'trading_reason': sys_detail.get('reason', ''),
        'trend_buy_type': trend_buy_type,
        'trend_bias': trend_bias,
        'mainline_level': mainline_level,
        'stop_loss': stop_loss,
        'stop_loss_pct': stop_loss_pct,
        'sector_chg': None,
        'sector_chg_5d': sector_chg_5d,
        'vs_sector_5d': vs_sector_5d,
        'score': score,
        'flags': flags,
        'triggered_signals': triggered_signals,
        'fusion_type': fusion_type,
        'fusion_reason': fusion_reason,
        'wave_position': wave_position,
        # 操作建议（卡片统一推导）
        'action_type': action_type,
        'action_signal': action_signal,
        'action_priority': action_priority,
        'action_reason': action_reason,
        'conclusion': '',
        'tags': [],
    }
    card['conclusion'] = _build_conclusion(card)
    card['tags'] = _build_tags(card)

    return card


def _empty_card(code, name, sector, direction, reason):
    """返回空卡片（数据不足时）"""
    return {
        'code': code,
        'name': name,
        'sector': sector,
        'direction': direction or '',
        'price': 0,
        'change': 0,
        'date': '',
        'structure': '--',
        'stage': '--',
        'ema': '--',
        'ema5': None,
        'ema10': None,
        'ema20': None,
        'ema30': None,
        'deviation_pct': 0,
        'vol_ratio': 0,
        'vol_analysis': '--',
        'signal': 'hold',
        'signal_text': '',
        'buy_point': '',
        'profit_model1': False,
        'trend_stock': False,
        'trading_system': '3l',
        'trading_reason': reason,
        'trend_buy_type': '',
        'trend_bias': '',
        'mainline_level': '',
        'stop_loss': None,
        'stop_loss_pct': None,
        'sector_chg': None,
        'sector_chg_5d': None,
        'vs_sector_5d': None,
        'score': 0,
        'flags': '',
        'triggered_signals': [],
        'fusion_type': '',
        'fusion_reason': '',
        'wave_position': '',
        'action_type': '持有',
        'action_signal': '',
        'action_priority': '中',
        'action_reason': '--',
        'conclusion': reason,
        'tags': [],
    }
