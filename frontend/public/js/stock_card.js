/**
 * 个股诊断卡公共渲染函数
 * 三个页面共用：review.html / monitor.html / stock_analysis.html
 * 
 * 用法：
 *   signalStockCard(s, idx) → HTML字符串
 *   s 的数据字段参见 generate_review_data.py 的 holdings_review / buy_signals_review
 */

/** 通用显示/隐藏切换（支持TR元素） */
function toggleChart(id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.display = el.style.display === 'none' ? (el.tagName === 'TR' ? 'table-row' : 'block') : 'none';
}
function signalStockCard(s, idx) {
    // 操作信号类
    const cls = s.signal === 'sell' ? 'danger' : s.signal === 'buy' ? 'warn' : 'hold';
    const signalText = s.signal === 'hold' ? '✅持有' : s.signal === 'buy' ? '⚡买入' : s.signal === 'sell' ? '❌卖出' : '--';
    // 阶段图标映射
    const stageIcons = {
        '上行': '↑', '加速': '🚀', '缩量整理': '🔄', '滞涨': '⚠️',
        '转弱': '📉', '下行': '↓', '加速跌': '📉', '转强': '📈',
        '区间底部': '🟢', '区间中段': '➡️', '区间顶部': '🔴'
    };
    const stageColors = {
        '上行': '#4ecdc4', '加速': '#e94560', '缩量整理': '#ffd700', '滞涨': '#ff6b6b',
        '转弱': '#ff6b6b', '下行': '#666', '加速跌': '#e94560', '转强': '#4ecdc4',
        '区间底部': '#4ecdc4', '区间中段': '#ffd700', '区间顶部': '#e94560'
    };
    const structIcons = {'上涨趋势': '📈', '区间震荡': '➡️', '下降趋势': '📉'};
    // 交易系统映射
    const isTrendSystem = s.trading_system === 'trend';
    const systemIcon = isTrendSystem ? '🔥' : '📘';
    const systemText = isTrendSystem ? '趋势交易' : '3L交易';
    const chartId = `hchart_${idx}`;
    const chartPrefix = isTrendSystem ? 'trend_' : '';
    const icon = stageIcons[s.stage] || '•';
    const color = stageColors[s.stage] || '#888';
    const structIcon = structIcons[s.structure] || '';
    // 买点标记（独立、显眼）
    const isBuy = s.signal === 'buy';
    const buyBadge = isBuy
        ? `<span style="background:#e94560;color:#fff;font-size:11px;font-weight:bold;padding:2px 8px;border-radius:4px;margin-left:6px;">🎯 买点</span>`
        : '';
    // 止损展示
    let stopLossHtml = '';
    if (s.stop_loss && s.stop_loss_pct !== undefined && s.stop_loss_pct !== null && s.stop_loss_pct !== '') {
        const sl = parseFloat(s.stop_loss);
        const pct = parseFloat(s.stop_loss_pct);
        const slColor = pct > 8 ? '#e94560' : pct > 5 ? '#ffd700' : '#4ecdc4';
        stopLossHtml = `<div class="field"><span class="l">止损:</span> <span class="v" style="color:${slColor};font-size:11px;">⬇ ${sl.toFixed(2)} (约${pct.toFixed(1)}%)</span></div>`;
    }
    // 买点显示：趋势股看乖离率区，3L股看原有买点
    let buyPointHtml = '';
    if (isTrendSystem) {
        // 趋势股不显示3L买点，改为显示BIAS区域
        const bias = s.trend_bias !== undefined && s.trend_bias !== '' ? parseFloat(s.trend_bias) : null;
        let zoneLabel = '';
        let zoneColor = '#888';
        if (bias !== null) {
            if (bias < 0 || bias <= 2) { zoneLabel = '乖离率买入区'; zoneColor = '#4ecdc4'; }
            else if (bias <= 8) { zoneLabel = '持有区'; zoneColor = '#ffd700'; }
            else { zoneLabel = '警戒区'; zoneColor = '#e94560'; }
            buyPointHtml = `<div class="field"><span class="l">区域:</span> <span class="v" style="color:${zoneColor};">📊 ${zoneLabel} BIAS=${bias.toFixed(2)}%</span></div>`;
        }
    } else if (s.buy_point) {
        buyPointHtml = `<div class="field"><span class="l">买点:</span> <span class="v">${s.buy_point}</span></div>`;
    }
    // 结论文字
    let conclusion = `阶段${s.stage}，${s.structure}`;
    let conclusionColor = '#aaa';
    const volDesc = s.vol_analysis || '';
    if (isBuy) {
        // 买点信号的结论行：加上止损信息
        const slText = (s.stop_loss && s.stop_loss_pct)
            ? `，建议止损${parseFloat(s.stop_loss).toFixed(2)}（约${parseFloat(s.stop_loss_pct).toFixed(1)}%）`
            : '';
        if (isTrendSystem) {
            const bias = s.trend_bias !== undefined && s.trend_bias !== '' ? parseFloat(s.trend_bias) : null;
            if (bias !== null && (bias < 0 || bias <= 2)) {
                conclusion = `BIAS5=${bias.toFixed(2)}%，乖离率买入区${slText}`;
            } else {
                conclusion = `${s.buy_point || '买点信号'}，${s.stage}阶段${slText}`;
            }
        } else {
            conclusion = `触发${s.buy_point}，${s.stage}阶段确认，可执行买入计划${slText}`;
        }
        conclusionColor = '#4ecdc4';
    } else if (isTrendSystem && s.trend_bias !== undefined && s.trend_bias !== '') {
        const bias = parseFloat(s.trend_bias);
        if (bias < 0) {
            conclusion = `BIAS5=${bias.toFixed(2)}%，价格在EMA5下方，乖离率买入区，属于趋势交易乖离率买点`;
            conclusionColor = '#4ecdc4';
        } else if (bias <= 2) {
            conclusion = `BIAS5=${bias.toFixed(2)}%，价格靠近EMA5，乖离率买入区，可考虑逢低吸纳`;
            conclusionColor = '#4ecdc4';
        } else if (bias <= 8) {
            conclusion = `BIAS5=${bias.toFixed(2)}%，价格在EMA5上方，持有区，趋势健康继续持有`;
            conclusionColor = '#ffd700';
        } else {
            conclusion = `⚠️ BIAS5=${bias.toFixed(2)}%，价格远离EMA5，警戒区，关注回调风险`;
            conclusionColor = '#e94560';
        }
    } else if (isTrendSystem) {
        conclusion = `趋势交易，${s.stage}阶段，${s.structure}`;
    } else if (s.signal === 'buy') {
        conclusion = `触发${s.buy_point}，${s.stage}阶段确认，可执行买入计划`;
    } else if (s.stage === '缩量整理') conclusion = `量能${volDesc}卖压枯竭，价在EMA10之上，中继蓄力形态，可持股等待放量突破`;
    else if (s.stage === '上行') conclusion = `斜率正常，EMA10持续向上，上行趋势健康，继续持有不动`;
    else if (s.stage === '加速') conclusion = `EMA10斜率加速变陡，拉升阶段，关注放量滞涨等左侧止盈信号`;
    else if (s.stage === '滞涨') conclusion = `EMA10走平涨不动${volDesc ? '，量能'+volDesc+'未有效萎缩' : ''}，警惕回调，考虑减仓`;
    else if (s.stage === '转弱') conclusion = `EMA10已拐头向下，趋势转弱，关注关键支撑位是否破位`;
    else if (s.stage === '区间底部') conclusion = `价格在支撑位附近，区间底部企稳，可考虑加仓博反弹`;
    else if (s.stage === '区间顶部') conclusion = `价格接近压力位，区间顶部受阻，注意减仓回避`;
    else if (s.stage === '区间中段') conclusion = `区间中部无明确方向，等待价格靠近支撑或压力再做决定`;
    // 标签（盈利1 + 趋势股）
    let tags = '';
    if (s.profit_model1) tags += '<span class="tag" style="background:#e94560;font-size:10px;padding:1px 6px;border-radius:4px;margin-left:4px;">🏆 盈利1</span>';
    if (s.trend_stock) tags += '<span class="tag" style="background:#2196f3;font-size:10px;padding:1px 6px;border-radius:4px;margin-left:4px;">📈 趋势股</span>';
    return `
        <div class="stock-item">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div><span class="name">${structIcon} ${s.name}</span>
                <span class="code">${s.code}</span>${tags}${buyBadge}</div>
                <span style="font-size:13px;color:${(s.change||0)>=0?'#ff4444':'#44aa44'};">
                    ${s.price!==undefined&&s.price!==null?s.price.toFixed(2):'--'} ${(s.change||0)>=0?'+':''}${s.change||0}%</span>
            </div>
            <div class="row" style="margin-top:6px;">
                <div class="field"><span class="l">方法:</span> <span class="v" title="${s.trading_reason||''}">${systemIcon}${systemText}</span></div>
                <div class="field"><span class="l">操作:</span> <span class="v ${cls}" style="font-weight:bold;">${signalText}</span></div>
                <div class="field"><span class="l">结构:</span> <span class="v">${structIcon} ${s.structure||'--'}</span></div>
                <div class="field"><span class="l">阶段:</span> <span class="v" style="color:${color};font-weight:bold;">${icon} ${s.stage||'--'}</span></div>
                ${buyPointHtml}
                ${stopLossHtml}
                <div class="field"><span class="l">板块:</span> <span class="v" style="color:#aaa;font-size:11px;">${s.sector||'--'}</span>${s.sector_chg !== undefined ? `<span style="color:${s.sector_chg>=0?'#ff4444':'#44aa44'};font-size:11px;margin-left:4px;">${s.sector_chg>=0?'+':''}${s.sector_chg.toFixed(2)}%</span>` : ''}${s.direction ? `<span style="color:#555;margin:0 4px;">|</span><span class="l">方向:</span> <span class="v" style="color:#4ecdc4;font-size:11px;">${s.direction}</span>` : ''}</div>
                ${s.mainline_level ? `<div class="field"><span class="l">定位:</span> <span class="v" style="color:${s.mainline_level==='主线'?'#e94560':s.mainline_level==='次级主线'?'#ffd700':'#666'};font-size:11px;">${s.mainline_level}</span></div>` : ''}
                <div class="field"><span class="l" style="cursor:pointer;color:#4ecdc4;" onclick="toggleChart('${chartId}')">📊</span></div>
            </div>
            <div style="margin-top:2px;font-size:11px;color:${conclusionColor};padding:2px 0;">💡 ${conclusion}</div>
            <div id="${chartId}" class="chart-container" style="display:none;margin-top:6px;">
                <object data="/api/stock-chart?code=${s.code}&t=${Date.now()}" type="image/svg+xml" style="width:100%;max-width:700px;border-radius:8px;"></object>
            </div>
        </div>
    `;
}

// 兼容 Node.js 测试环境
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { signalStockCard };
}
