    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth()+1).padStart(2,'0');
    const d = String(today.getDate()).padStart(2,'0');
    const wds = ['日','一','二','三','四','五','六'];
    document.getElementById('todayDate').textContent = `${y}-${m}-${d} 星期${wds[today.getDay()]}`;

    let reviewData = {};

    // ====== 加载复盘数据 ======
    function loadReviewData(date) {
        fetch(`/api/review/${date}`)
            .then(r => r.json())
            .then(data => {
                reviewData = data;
                // ① 大盘判定
                if (data.market) updateMarketUI(data.market);
                // ② 主线（主+次级）
                if (data.mainline) updateMainlineUI(data.mainline);
                // ③ 持仓复盘
                if (data.holdings_review) updateStocksUI(data.holdings_review);
                else if (data.holdings) updateStocksUI(data.holdings);
                // ④ 自选股买点信号
                if (data.buy_signals_review || data.holdings_review) updateBuySignalsUI();
                // PLAN 交易计划
                if (data.trading_plan) updateTradingPlanUI(data.trading_plan);
                // ① 图表：有存档路径则更新
                if (data.charts) {
                    document.getElementById('indexChartObj').data = data.charts.index_chart;
                    document.getElementById('fundFlowImg').src = data.charts.fund_flow;
                } else {
                    document.getElementById('indexChartObj').data = '/review_charts/zzqz_v2.svg';
                    document.getElementById('fundFlowImg').src = '/charts/fund_flow_chart.png';
                }
            })
            .catch(() => {
                refreshMarket();
            });
    }

    // ====== 历史列表 ======
    function loadHistoryList(currentDisplayDate) {
        const list = document.getElementById('historyReviewList');
        fetch('/api/review/dates')
            .then(r => r.json())
            .then(data => {
                const curDate = currentDisplayDate || document.querySelector('.header .date-badge')?.textContent?.split(' ')[0] || '';
                const dates = (data.dates || []).filter(d => d !== curDate);
                if (dates.length === 0) {
                    list.innerHTML = '<div class="empty">暂无历史复盘数据</div>';
                    return;
                }
                list.innerHTML = '<div style="display:flex;flex-direction:column;gap:6px;">' +
                    dates.sort().reverse().map(date => `
                        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 10px;background:rgba(255,255,255,0.02);border-radius:8px;">
                            <span style="color:#e94560;font-size:13px;font-weight:bold;">${date}</span>
                            <a href="/review.html?date=${date}" style="color:#4ecdc4;text-decoration:none;font-size:12px;">查看复盘 →</a>
                        </div>
                    `).join('') + '</div>';
            })
            .catch(() => {
                list.innerHTML = '<div class="empty">暂无历史复盘数据</div>';
            });
    }

    function checkUrlParam() {
        const params = new URLSearchParams(window.location.search);
        const dateParam = params.get('date');
        if (dateParam) {
            document.querySelector('.header .date-badge').textContent = `${dateParam} 历史复盘`;
            loadReviewData(dateParam);
            loadHistoryList(dateParam);
            return true;
        }
        return false;
    }

    // ====== ① 大盘判定 ======
    function refreshMarket() {
        fetch('/api/market')
            .then(r => r.json())
            .then(data => updateMarketUI(data))
            .catch(() => {
                document.getElementById('marketPrice').textContent = '--';
                document.getElementById('cyclePos').textContent = '波中';
                document.getElementById('positionLevel').textContent = '半仓';
                document.getElementById('strategy').textContent = '中等仓位·精选个股';
            });
    }

    function updateMarketUI(data) {
        const price = document.getElementById('marketPrice');
        const chg = document.getElementById('marketChange');
        const cycle = document.getElementById('cyclePos');
        const pos = document.getElementById('positionLevel');
        const strat = document.getElementById('strategy');
        const rule = document.getElementById('positionRule');
        const advice = document.getElementById('strategyAdvice');

        if (data.price) {
            price.textContent = data.price;
            price.className = 'value' + ((data.change || 0) >= 0 ? ' up' : ' down');
            chg.textContent = `${(data.change || 0) >= 0 ? '+' : ''}${data.change}%`;
        }
        if (data.score !== undefined) {
            document.getElementById('cycleScore').textContent = `综合评分 ${data.score}`;
        }
        if (data.position) {
            // 后端返回中文位置名(波中偏上/偏波谷等)，直接用 data.strategy 和 data.position_pct
            cycle.textContent = data.position;
            pos.textContent = data.position_pct || '--';
            strat.textContent = data.strategy || '--';
            if (data.build_per_stock_pct) rule.textContent = `建仓 ${data.build_per_stock_pct}%/只`;
            advice.textContent = data.strategy || '--';
        }

        // V5波峰波谷判定 — 条件明细
        const pk = data.pk_score || 0;
        const vl = data.vl_score || 0;
        const posName = data.position || '波中';
        const tbody = document.getElementById('scoreDetailBody');
        tbody.innerHTML = `
          <tr><td colspan="3" style="font-size:13px;color:#4ecdc4;font-weight:bold;padding-bottom:8px;">
            ${posName}
          </td></tr>
          <tr>
            <td style="color:#888;width:50px;">波峰</td>
            <td style="width:50px;text-align:center;font-size:16px;">
              ${pk>=4?'🟢':pk>=3?'🟡':pk>=1?'⚪':'⚪'}
            </td>
            <td style="color:#888;font-size:11px;">
              ${pk>=4?'✅ 趋势转跌+位置偏高+量价异常+方向确认 → 高度确信':
                pk>=3?'⚠️ 满足3个条件，可能偏峰':
                pk>=1?'🔸 满足1个条件，趋势有波动':
                '— 无波峰信号'}
            </td>
          </tr>
          <tr>
            <td style="color:#888;">波谷</td>
            <td style="text-align:center;font-size:16px;">
              ${vl>=4?'🟢':vl>=3?'🟡':vl>=1?'⚪':'⚪'}
            </td>
            <td style="color:#888;font-size:11px;">
              ${vl>=4?'✅ 趋势转涨+位置偏低+恐慌出清+方向确认 → 高度确信':
                vl>=3?'⚠️ 满足3个条件，可能偏谷':
                vl>=1?'🔸 满足1个条件':
                '— 无波谷信号'}
            </td>
          </tr>
          <tr><td colspan="3" style="border-top:1px solid #333;padding-top:6px;"></td></tr>
          <tr>
            <td style="color:#888;">①趋势</td>
            <td style="text-align:center;">${pk>=1?'✅':'❌'}</td>
            <td style="color:#888;font-size:11px;">前期bias上升+近期走平/掉头</td>
          </tr>
          <tr>
            <td style="color:#888;">②位置</td>
            <td style="text-align:center;">${pk>=2?'✅':'❌'}</td>
            <td style="color:#888;font-size:11px;">MA20乖离率&gt;+1.5% (当前: ${typeof data.bias20==='number'?data.bias20.toFixed(1):'?'}%)</td>
          </tr>
          <tr>
            <td style="color:#888;">③量价</td>
            <td style="text-align:center;">${pk>=3?'✅':'❌'}</td>
            <td style="color:#888;font-size:11px;">放量滞涨/长上影/加速衰竭</td>
          </tr>
          <tr>
            <td style="color:#888;">④方向</td>
            <td style="text-align:center;">${pk>=4?'✅':'❌'}</td>
            <td style="color:#888;font-size:11px;">乖离率3日变化转负 (${typeof data.bias20_chg_3d==='number'?data.bias20_chg_3d.toFixed(1):'?'}%)</td>
          </tr>
          <tr><td colspan="3" style="text-align:center;color:#555;font-size:11px;padding-top:6px;">
            pk≥4=峰 &nbsp; pk≥3=近峰 &nbsp; vl≥4=谷 &nbsp; vl≥3=近谷 &nbsp; 其余=波中
          </td></tr>
        `;
    }

    // ====== ③ 主线（主+次级+轮动监测） ======
    function updateMainlineUI(data) {
        const container = document.getElementById('mainlineContainer');
        if (!data) {
            container.innerHTML = '<div class="empty">暂无主线数据</div>';
            return;
        }
        const primary = data.lines || [];
        const secondary = data.secondary || [];
        const persist = data.persistence || [];
        const allRanked = data.all_ranked || [];
        const top10 = allRanked.slice(0, 10);

        // 持续天数
        const persistDays = {};
        persist.forEach(p => { persistDays[p.name] = p.days; });

        const mainNames = new Set(primary.map(l => l.name));
        const secNames = new Set(secondary.map(l => l.name));

        // 1. 先渲染基础内容（徽章+排名表）
        let html = '<div id="mainlineBaseContent">';  // 用于异步更新时不闪烁
        // 轮动提示占位
        html += '<div id="rotationBanner" style="margin-bottom:10px;min-height:20px;"></div>';

        // === 主线徽章 ===
        if (primary.length > 0) {
            html += `<div style="margin-bottom:12px;"><span style="color:#e94560;font-weight:600;font-size:14px;">🔴 主线</span>
                     <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:6px;">`;
            primary.forEach(l => {
                const days = persistDays[l.name] || 0;
                html += `<span style="background:rgba(233,69,96,0.15);border:1px solid #e94560;border-radius:6px;padding:4px 12px;font-size:13px;color:#e94560;">
                            ${l.name} <span style="font-size:11px;color:#888;">+${l.chg_20d.toFixed(1)}% ${days>0?'·'+days+'天':''}</span>
                         </span>`;
            });
            html += `</div></div>`;
        }

        // === 次级主线徽章 ===
        if (secondary.length > 0) {
            html += `<div style="margin-bottom:12px;"><span style="color:#ffd700;font-weight:600;font-size:14px;">🟡 次级主线</span>
                     <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:6px;">`;
            secondary.forEach(l => {
                const days = persistDays[l.name] || 0;
                html += `<span style="background:rgba(255,215,0,0.1);border:1px solid rgba(255,215,0,0.3);border-radius:6px;padding:4px 12px;font-size:13px;color:#ffd700;">
                            ${l.name} <span style="font-size:11px;color:#888;">+${l.chg_20d.toFixed(1)}% ${days>0?'·'+days+'天':''}</span>
                         </span>`;
            });
            html += `</div></div>`;
        }

        // === 排名表（带变动列，初始空，异步填充） ===
        html += `<table><thead><tr>
            <th>#</th><th>行业</th><th>20日涨幅</th><th>变动</th><th>持续天数</th><th>标签</th>
        </tr></thead><tbody id="mainlineRankBody">`;
        top10.forEach((l, i) => {
            const days = persistDays[l.name] || 0;
            let tag = '<span class="tag gray">其他</span>';
            if (mainNames.has(l.name)) tag = '<span class="tag red">主线</span>';
            else if (secNames.has(l.name)) tag = '<span class="tag" style="background:rgba(255,215,0,0.15);color:#ffd700;border:1px solid rgba(255,215,0,0.3);">次级</span>';
            // 变动列先显示加载中
            html += `<tr>
                <td>${i+1}</td>
                <td style="font-weight:600;">${l.name}</td>
                <td style="color:${l.chg_20d>=0?'#ff4444':'#44aa44'}">${l.chg_20d>=0?'+':''}${l.chg_20d.toFixed(1)}%</td>
                <td id="rankChg_${i}" style="font-size:11px;color:#555;">加载中...</td>
                <td>${days>0?days+'天':'--'}</td>
                <td>${tag}</td>
            </tr>`;
        });
        html += `</tbody></table>`;
        html += `<div style="margin-top:8px;color:#555;font-size:10px;text-align:right;">
            20日涨幅排序 · 前5=主线 · 6~10=次级主线
        </div>`;
        html += '</div>'; // close mainlineBaseContent
        container.innerHTML = html;

        // 2. 异步加载昨天数据来对比变动
        const dates = (window._reviewDates || []).filter(d => d !== reviewData.date);
        const prevDate = dates.length > 0 ? dates[0] : null;
        if (!prevDate) {
            top10.forEach((_, i) => {
                const el = document.getElementById('rankChg_'+i);
                if (el) el.textContent = '--';
            });
            return;
        }
        fetch(`/api/review/${prevDate}`)
            .then(r => r.json())
            .then(prev => {
                const prevRanked = (prev.mainline && prev.mainline.all_ranked) || [];
                const prevTop10 = prevRanked.slice(0, 10);
                const prevNames = prevTop10.map(l => l.name);

                // 计算轮动
                const todayNames = top10.map(l => l.name);
                const newEntry = todayNames.filter(n => !prevNames.includes(n));
                const gone = prevNames.filter(n => !todayNames.includes(n));

                // 渲染轮动提示
                const banner = document.getElementById('rotationBanner');
                let bHtml = '';
                if (newEntry.length > 0 || gone.length > 0) {
                    if (newEntry.length > 0) {
                        bHtml += `<span style="color:#4ecdc4;">🆕 新进前10: ${newEntry.join(' · ')}</span>`;
                    }
                    if (gone.length > 0) {
                        if (bHtml) bHtml += ' &nbsp;|&nbsp; ';
                        bHtml += `<span style="color:#e94560;">📉 跌出前10: ${gone.join(' · ')}</span>`;
                    }
                } else {
                    bHtml = `<span style="color:#888;font-size:12px;">↔️ 前10名无变化</span>`;
                }
                if (banner) banner.innerHTML = bHtml;

                // 渲染变动列
                top10.forEach((l, i) => {
                    const el = document.getElementById('rankChg_'+i);
                    if (!el) return;
                    const idx = prevNames.indexOf(l.name);
                    if (idx === i) {
                        el.innerHTML = '<span style="color:#555;">—</span>';
                    } else if (idx >= 0) {
                        const dir = idx > i ? '↑' : '↓';
                        const steps = Math.abs(idx - i);
                        const color = idx > i ? '#4ecdc4' : '#e94560';
                        el.innerHTML = `<span style="color:${color};">${dir}${steps} (昨#${idx+1})</span>`;
                    } else {
                        el.innerHTML = '<span style="color:#4ecdc4;">🆕新进</span>';
                    }
                });

                // 补全30名以后的变动
                allRanked.slice(10).forEach((l, i) => {
                    const idx = prevNames.indexOf(l.name);
                    // 这一部分如果没有变动显示, 也可以不需要
                });
            })
            .catch(() => {
                top10.forEach((_, i) => {
                    const el = document.getElementById('rankChg_'+i);
                    if (el) el.textContent = '--';
                });
            });
    }

    // ====== ③ 持仓个股复盘（不分页，按方向Tab分类展示） ======
    function updateStocksUI(stocks) {
        const container = document.getElementById('stockReviewList');
        if (!stocks || stocks.length === 0) {
            container.innerHTML = '<div class="empty">暂无持仓数据</div>';
            return;
        }
        // 方向颜色（与买点信号Tab一致）
        const secColors = {
            '半导体': '#e94560', '算力': '#2196f3', '创新药': '#4CAF50',
            '机器人': '#9C27B0', '新能源': '#FF9800', '资源股': '#8B4513',
            'AI应用': '#00BCD4', '商业航天': '#FF5722',
        };
        // 按方向分组
        const groups = {};
        stocks.forEach(s => {
            const sec = s.sector || '其他';
            if (!groups[sec]) groups[sec] = [];
            groups[sec].push(s);
        });
        const secNames = Object.keys(groups).sort();
        // 固定方向顺序
        const secOrder = ['算力','半导体','机器人','新能源','商业航天','AI应用','资源股','创新药'];
        const sortedNames = secOrder.filter(s => secNames.includes(s)).concat(secNames.filter(s => !secOrder.includes(s)));
        // Tab状态
        if (!window._holdTab) window._holdTab = { activeSector: sortedNames[0] };
        const tab = window._holdTab;
        if (!sortedNames.includes(tab.activeSector)) tab.activeSector = sortedNames[0];
        // Tab导航
        let html = '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px;border-bottom:1px solid #333;padding-bottom:6px;">';
        sortedNames.forEach(sec => {
            const active = sec === tab.activeSector;
            const color = secColors[sec] || '#888';
            html += `<span style="cursor:pointer;padding:4px 12px;font-size:12px;border-radius:12px;display:inline-block;${active ? `background:${color};color:#fff;` : `color:${color};background:rgba(255,255,255,0.05);`}" onclick="window._holdTab.activeSector='${sec}';updateStocksUI(reviewData.holdings_review || reviewData.holdings || []);">${sec} (${groups[sec].length})</span>`;
        });
        html += '</div>';
        // 当前Tab数据，用signalStockCard渲染
        const activeData = groups[tab.activeSector] || [];
        html += activeData.map((s, i) => {
            const card = signalStockCard(s, i + 1);
            return card.replace(/id="hchart_/g, 'id="hchart_h_').replace(/toggleChart\('hchart_/g, "toggleChart('hchart_h_");
        }).join('');
        html += '<div style="margin-top:6px;text-align:right;color:#555;font-size:11px;">共' + stocks.length + '只持仓</div>';
        container.innerHTML = html;
    }


    // ====== ④ 自选股买点信号 ======
    function updateBuySignalsUI() {
        const container = document.getElementById('buySignalList');
        const signals = reviewData.buy_signals_review || [];
        if (!signals.length) {
            container.innerHTML = '<div class="empty">暂无买点信号</div>';
            return;
        }
        // 按方向分组（sector 已为用户方向）
        const groups = {};
        signals.forEach(s => {
            const sec = s.sector || '其他';
            if (!groups[sec]) groups[sec] = [];
            groups[sec].push(s);
        });
        const secNames = Object.keys(groups).sort();
        // 固定方向顺序（与持仓区一致）
        const secOrder = ['算力','半导体','机器人','新能源','商业航天','AI应用','资源股','创新药'];
        const sortedNames = secOrder.filter(s => secNames.includes(s)).concat(secNames.filter(s => !secOrder.includes(s)));
        // 方向颜色
        const secColors = {
            '半导体': '#e94560', '算力': '#2196f3', '创新药': '#4CAF50',
            '机器人': '#9C27B0', '新能源': '#FF9800', '资源股': '#8B4513',
            'AI应用': '#00BCD4', '商业航天': '#FF5722',
        };
        // Tab 状态（保留用户已选的Tab，新方向出现时追加）
        if (!window._buyTab) window._buyTab = { activeSector: sortedNames[0], pages: {} };
        const tab = window._buyTab;
        if (!sortedNames.includes(tab.activeSector)) tab.activeSector = sortedNames[0];
        // 构建Tabs（用span替代a标签避免javascript:显示问题）
        let html = '<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:10px;border-bottom:1px solid #333;padding-bottom:6px;">';
        sortedNames.forEach((sec, i) => {
            const active = sec === tab.activeSector;
            const color = secColors[sec] || '#888';
            html += `<span style="cursor:pointer;padding:4px 12px;font-size:12px;border-radius:12px;text-decoration:none;display:inline-block;${active?`background:${color};color:#fff;`:`color:${color};background:rgba(255,255,255,0.05);`}" onclick="window._buyTab.activeSector='${sec}';window._buyTab.pages['${sec}']=1;updateBuySignalsUI();">${sec} (${groups[sec].length})</span>`;
        });
        html += '</div>';
        // 当前Tab数据
        const activeData = groups[tab.activeSector] || [];
        // 分页
        if (!tab.pages[tab.activeSector]) tab.pages[tab.activeSector] = 1;
        const page = tab.pages[tab.activeSector];
        const perPage = 10;
        const total = activeData.length;
        const totalPages = Math.ceil(total / perPage) || 1;
        const start = (page - 1) * perPage;
        const end = Math.min(start + perPage, total);
        const pageData = activeData.slice(start, end);
        // 用 signalStockCard 渲染（同第④部分，图表ID加前缀防冲突）
        html += pageData.map((s, i) => {
            const card = signalStockCard(s, start + i + 1);
            return card.replace(/id="hchart_/g, 'id="bchart_').replace(/toggleChart\('hchart_/g, "toggleChart('bchart_");
        }).join('');
        // 分页控件
        if (totalPages > 1) {
            const pKey = tab.activeSector;
            html += '<div style="display:flex;justify-content:center;align-items:center;gap:8px;margin-top:10px;font-size:12px;">';
            html += '<span style="color:#888;">共' + total + '只</span>';
            if (page > 1) html += '<a href="javascript:;" onclick="window._buyTab.pages[\'' + pKey + '\']=' + (page-1) + ';updateBuySignalsUI();return false;" style="color:#4ecdc4;text-decoration:none;">‹ 上一页</a>';
            html += '<span style="color:#e94560;font-weight:600;">' + page + '/' + totalPages + '</span>';
            if (page < totalPages) html += '<a href="javascript:;" onclick="window._buyTab.pages[\'' + pKey + '\']=' + (page+1) + ';updateBuySignalsUI();return false;" style="color:#4ecdc4;text-decoration:none;">下一页 ›</a>';
            html += '</div>';
        }
        container.innerHTML = html;
    }

    // ====== PLAN 每日交易计划（3L体系标准版） ======
    function updateTradingPlanUI(plan) {
        const container = document.getElementById('tradingPlanArea');
        if (!plan) {
            container.innerHTML = '<div class="empty">暂无交易计划</div>';
            return;
        }

        let html = `<div class="plan-card">`;

        // 策略总览
        html += `<div class="plan-title">📌 ${plan.overall_strategy || '正常交易'}</div>`;
        html += `<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px;">`;
        html += `<span style="font-size:13px;"><span style="color:#888;">仓位:</span> ${plan.position_level || '--'}</span>`;
        html += `<span style="font-size:13px;"><span style="color:#888;">建仓:</span> ${plan.build_per_stock_pct || '--'}</span>`;
        if (plan.main_lines && plan.main_lines.length > 0) {
            html += `<span style="font-size:13px;"><span style="color:#888;">主线:</span> ${plan.main_lines.join(' · ')}</span>`;
        }
        html += `</div>`;

        // 仓位规则说明
        if (plan.position_detail) {
            html += `<div style="margin-bottom:12px;padding:6px 10px;background:rgba(78,205,196,0.08);border-radius:6px;font-size:12px;color:#4ecdc4;">`;
            html += `📋 ${plan.position_detail}`;
            html += `</div>`;
        }

        // 个股操作建议
        if (plan.holdings_action && plan.holdings_action.length > 0) {
            html += `<div style="margin-bottom:8px;"><strong style="color:#4ecdc4;font-size:13px;">📦 个股操作</strong></div>`;
            const priColors = {'高':'#e94560','中':'#ffd700','低':'#888'};
            plan.holdings_action.forEach(item => {
                const color = priColors[item.priority] || '#888';
                html += `<div class="plan-item" style="border-left:3px solid ${color};padding-left:8px;margin-bottom:4px;">`;
                html += `<span style="font-weight:600;">${item.stock}</span>`;
                html += ` <span style="color:${color};">→ ${item.action}</span>`;
                html += ` <span style="color:#888;font-size:11px;">${item.reason}</span>`;
                html += `<span style="color:${color};font-size:10px;margin-left:6px;">${item.priority}</span>`;
                html += `</div>`;
            });
        }

        // 买点关注优先级
        if (plan.buy_priority && plan.buy_priority.length > 0) {
            html += `<div style="margin-bottom:6px;margin-top:12px;"><strong style="color:#ffd700;font-size:13px;">🎯 关注买点（优先级排序）</strong></div>`;
            plan.buy_priority.forEach((s, i) => {
                const tag = s.is_main ? '<span class="tag red" style="font-size:10px;">主线</span>' : '';
                const pm1 = s.profit_model1 ? '<span class="tag" style="background:#e94560;font-size:10px;padding:1px 6px;">🏆</span>' : '';
                const trend = s.trend_stock ? '<span class="tag" style="background:#2196f3;font-size:10px;padding:1px 6px;">📈</span>' : '';
                const chgColor = s.change >= 0 ? '#ff4444' : '#44aa44';
                html += `<div class="plan-item" style="font-size:12px;">`;
                html += `<span style="color:#e94560;font-weight:bold;">#${i+1}</span>`;
                html += ` <span style="font-weight:600;">${s.name}</span>`;
                html += ` <span style="color:#888;">${s.buy_point}</span>`;
                html += ` ${tag} ${pm1} ${trend}`;
                html += ` <span style="color:${chgColor};">${s.change >= 0 ? '+' : ''}${s.change}%</span>`;
                html += `</div>`;
            });
        }

        // 风险项
        if (plan.risk_items && plan.risk_items.length > 0) {
            html += `<div style="margin-top:12px;">`;
            plan.risk_items.forEach(item => {
                const isRed = item.includes('🔴');
                html += `<div style="padding:5px 8px;margin:3px 0;border-radius:4px;font-size:12px;${isRed ? 'background:rgba(233,69,96,0.08);color:#e94560;' : 'background:rgba(255,255,255,0.02);color:#aaa;'}">${item}</div>`;
            });
            html += `</div>`;
        }

        html += `</div>`;
        container.innerHTML = html;
    }




    

    

    

    
    // ====== 工具函数 ======
    function toggleEl(id) {
        const el = document.getElementById(id);
        if (!el) return;
        el.style.display = el.style.display === 'none' ? '' : 'none';
    }

    function toggleIndexChart() {
        const chart = document.getElementById('indexChart');
        const obj = document.getElementById('indexChartObj');
        if (!chart || !obj) return;
        const isHidden = chart.style.display === 'none';
        chart.style.display = isHidden ? '' : 'none';
        if (isHidden) {
            obj.data = obj.data.split('?')[0] + '?t=' + Date.now();
        }
    }

    // ====== 初始加载 ======
    if (!checkUrlParam()) {
        loadLatestReview();
    }

    function loadLatestReview() {
        fetch('/api/review/dates')
            .then(r => r.json())
            .then(dd => {
                const dates = (dd.dates || []).sort().reverse();
                window._reviewDates = dates;  // 全局日期列表，供主线变动对比用
                if (dates.length > 0) {
                    const today = `${y}-${m}-${d}`;
                    const nowHour = new Date().getHours();
                    // 如果最新日期是今天，但还没到18:00（cron未运行），自动降级到上一个交易日
                    let latest = dates[0];
                    if (latest === today && nowHour < 18 && dates.length > 1) {
                        latest = dates[1];
                    }
                    const isToday = latest === today;
                    document.querySelector('.header .date-badge').textContent =
                        isToday ? `${latest} 今日复盘 ✓` : `${latest} 每日复盘（收盘后自动更新）`;
                    loadReviewData(latest);
                    loadHistoryList(latest);
                } else {
                    document.querySelector('.header .date-badge').textContent = '暂无复盘数据';
                    refreshMarket();
                }
            })
            .catch(() => {
                refreshMarket();
            });
    }