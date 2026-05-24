const DIRECTIONS = ['全部','半导体','算力','机器人','新能源','创新药','AI应用','商业航天','资源股','其他'];
    let enrichedData = null;  // {stocks: [...]} enriched with price/change/structure/stage
    let trendCodes = new Set();
    let activeDir = '全部';
    let searchTimer = null;

    const toast = document.getElementById('toast');
    function showToast(msg, isError) {
        toast.textContent = msg;
        toast.style.borderColor = isError ? '#e94560' : '#22c55e';
        toast.style.color = isError ? '#e94560' : '#22c55e';
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 2000);
    }

    // signalStockCard 需要的图表切换函数
    async function loadData() {
        try {
            const [r1, r2] = await Promise.all([
                fetch('/api/watchlist/analysis'),
                fetch('/api/trend-tracked')
            ]);
            enrichedData = await r1.json();
            const td = await r2.json();
            trendCodes = new Set((td.candidates || []).map(c => c.code));
            render();
        } catch(e) {
            document.getElementById('cardsArea').innerHTML = '<div class="empty">❌ 加载失败</div>';
        }
    }

    function render() {
        if (!enrichedData) return;
        const stocks = enrichedData.stocks || [];
        document.getElementById('stats').innerHTML = `共 <b>${stocks.length}</b> 只自选股 · 趋势 ${trendCodes.size} 只`;
        renderDirTabs(stocks);
        renderCards();
    }

    function renderDirTabs(stocks) {
        const counts = {};
        DIRECTIONS.forEach(d => counts[d] = 0);
        stocks.forEach(s => { const d = s.direction || '其他'; counts[d] = (counts[d] || 0) + 1; });
        document.getElementById('dirTabs').innerHTML = DIRECTIONS.map(d => {
            const cnt = counts[d] || 0;
            const active = d === activeDir ? ' active' : '';
            const label = d === '全部' ? `全部 (${stocks.length})` : `${d} (${cnt})`;
            return `<div class="dir-tab${active}" onclick="switchDir('${d}')">${label}</div>`;
        }).join('');
    }

    function renderCards() {
        const stocks = enrichedData.stocks || [];
        const filter = document.getElementById('filterInput').value.trim().toLowerCase();
        let filtered = stocks.filter(s => {
            if (activeDir !== '全部' && s.direction !== activeDir) return false;
            if (filter && !s.code.includes(filter) && !(s.name||'').toLowerCase().includes(filter)) return false;
            return true;
        });

        // 按结构排序：上涨趋势→区间震荡→下降趋势，同类结构内按方向
        const structOrder = {'上涨趋势': 0, '区间震荡': 1, '下降趋势': 2};
        const dirOrder = ['半导体','算力','机器人','新能源','创新药','AI应用','商业航天','资源股','其他'];
        filtered.sort((a, b) => {
            const sa = structOrder[a.structure] ?? 3;
            const sb = structOrder[b.structure] ?? 3;
            if (sa !== sb) return sa - sb;
            const ai = dirOrder.indexOf(a.direction || '其他');
            const bi = dirOrder.indexOf(b.direction || '其他');
            return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
        });

        if (filtered.length === 0) {
            document.getElementById('cardsArea').innerHTML = '<div class="empty">无匹配股票</div>';
            return;
        }

        let html = '';
        filtered.forEach((s, i) => {
            // 构建signalStockCard所需的数据
            const cardData = {
                name: s.name || s.code,
                code: s.code,
                price: s.price,
                change: s.change,
                signal: s.signal || 'hold',
                structure: s.structure || '--',
                stage: s.stage || '--',
                sector: s.sector || '--',
                direction: s.direction || '其他',
                trading_system: s.trading_system || '3l',
                trend_bias: s.trend_bias,
                buy_point: s.buy_point || '',
                profit_model1: s.profit_model1 || false,
                trend_stock: s.trend_stock || false,
                vol_analysis: s.vol_analysis || '',
            };
            const cardHtml = signalStockCard(cardData, 'wl_' + i);
            // 把方向选择和删除按钮放在卡片底部，嵌入卡片内部（在最后</div>之前）
            const dirOptions = DIRECTIONS.filter(d => d !== '全部').map(d =>
                `<option value="${d}" ${s.direction === d ? 'selected' : ''}>${d}</option>`
            ).join('');
            const footerHtml = `<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0 0;margin-top:4px;border-top:1px solid rgba(42,42,78,0.4);">
                <div style="display:flex;gap:6px;align-items:center;">
                    <select class="dir-select" onchange="changeDir('${s.code}', this.value)" style="width:68px;">
                        ${dirOptions}
                    </select>
                </div>
                <button class="btn btn-red btn-sm" onclick="removeStock('${s.code}')" style="cursor:pointer;">✕ 删除</button>
            </div>`;
            const lastDiv = cardHtml.lastIndexOf('</div>');
            const modifiedCard = cardHtml.substring(0, lastDiv) + footerHtml + cardHtml.substring(lastDiv);
            html += modifiedCard;
        });

        document.getElementById('cardsArea').innerHTML = html;
    }

    function switchDir(d) { activeDir = d; renderCards(); renderDirTabs(enrichedData.stocks || []); }

    // 搜索股票
    function searchStock(q) {
        clearTimeout(searchTimer);
        const el = document.getElementById('searchResults');
        if (!q || q.length < 1) { el.style.display = 'none'; return; }
        searchTimer = setTimeout(async () => {
            try {
                const r = await fetch('/api/watchlist/search?q=' + encodeURIComponent(q));
                const data = await r.json();
                if (!data.results || data.results.length === 0) {
                    el.innerHTML = '<div class="search-result-item" style="color:#888;">无结果</div>';
                    el.style.display = 'block';
                    return;
                }
                el.innerHTML = data.results.map(st =>
                    `<div class="search-result-item" onclick="selectSearchResult('${st.code}','${st.name}','${st.direction}')">
                        <span><span class="sr-name">${st.name}</span> <span class="sr-code">${st.code}</span></span>
                        <span class="sr-ind">${st.industry||''} · ${st.direction}</span>
                    </div>`
                ).join('');
                el.style.display = 'block';
            } catch(e) { el.style.display = 'none'; }
        }, 300);
    }

    function selectSearchResult(code, name, dir) {
        document.getElementById('addSearch').value = code + ' ' + name;
        document.getElementById('addDir').value = dir;
        document.getElementById('searchResults').style.display = 'none';
        window._selectedCode = code;
        window._selectedName = name;
    }

    async function addStock() {
        const code = window._selectedCode;
        const name = window._selectedName;
        if (!code) { showToast('⚠️ 请先搜索选择股票', true); return; }
        const dir = document.getElementById('addDir').value;

        // 检查是否已存在
        if ((enrichedData.stocks || []).some(s => s.code === code)) {
            showToast(`⚠️ ${name}(${code}) 已在自选股中`, true);
            return;
        }

        // 获取行业
        let industry = '';
        try {
            const r = await fetch('/api/watchlist/search?q=' + code);
            const data = await r.json();
            if (data.results && data.results[0]) industry = data.results[0].industry || '';
        } catch(e) {}

        // 重新拉取全量数据确保同步
        try {
            const r = await fetch('/api/watchlist/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    stocks: [...(enrichedData.stocks || []), {code, name, direction: dir, industry}],
                    count: (enrichedData.stocks || []).length + 1,
                }),
            });
            const data = await r.json();
            if (data.success) {
                showToast(`✅ 已添加 ${name}(${code})`);
                document.getElementById('addSearch').value = '';
                window._selectedCode = null;
                window._selectedName = null;
                document.getElementById('searchResults').style.display = 'none';
                // 重新加载全量数据
                const ra = await fetch('/api/watchlist/analysis');
                enrichedData = await ra.json();
                render();
            } else {
                showToast('⚠️ 添加失败', true);
            }
        } catch(e) {
            showToast('⚠️ 添加失败: ' + e.message, true);
        }
    }

    async function changeDir(code, newDir) {
        const s = (enrichedData.stocks || []).find(x => x.code === code);
        if (s) {
            s.direction = newDir;
            await saveWatchlist();
            showToast(`✅ ${s.name||code} 方向改为 ${newDir}`);
        }
    }

    async function removeStock(code) {
        const s = (enrichedData.stocks || []).find(x => x.code === code);
        if (!s) return;
        if (!confirm(`确认删除 ${s.name||code} ？`)) return;
        enrichedData.stocks = enrichedData.stocks.filter(x => x.code !== code);
        await saveWatchlist();
        showToast(`❌ 已删除 ${s.name||code}`);
    }

    async function saveWatchlist() {
        const stocks = (enrichedData.stocks || []).map(s => ({
            code: s.code, name: s.name, direction: s.direction, industry: s.industry || ''
        }));
        try {
            const r = await fetch('/api/watchlist/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({stocks, count: stocks.length}),
            });
            const data = await r.json();
            if (data.success) render();
            else showToast('⚠️ 保存失败', true);
        } catch(e) {
            showToast('⚠️ 保存失败: ' + e.message, true);
        }
    }

    loadData();