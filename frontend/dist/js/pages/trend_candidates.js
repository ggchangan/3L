const PAGE_SIZE = 10;
    let rawData = null;
    let activeMain = 'main';
    let activeInd = null;
    let curPage = 1;
    const toast = document.getElementById('toast');

    // 图表切换（signalStockCard需要）
    function showToast(msg) {
        toast.textContent = msg;
        toast.classList.add('show');
        setTimeout(() => toast.classList.remove('show'), 2000);
    }

    async function loadData() {
        try {
            const r = await fetch('/api/trend-candidates');
            rawData = await r.json();
            // 也拉取已跟踪列表
            const rt = await fetch('/api/trend-tracked');
            rawData._tracked = await rt.json();
            render();
        } catch(e) {
            document.getElementById('cardsArea').innerHTML = '<div class="empty">❌ 加载失败</div>';
        }
    }

    function render() {
        if (!rawData) return;
        const main = rawData.main_lines || [];
        const sub = rawData.sub_main_lines || [];
        const total = rawData.count || 0;
        document.getElementById('stats').innerHTML = `共 <b>${total}</b> 只候选 · 主线 ${sumCnt(main)} 只 · 次级 ${sumCnt(sub)} 只 · 已跟踪 ${getTrackedCount()} 只`;

        // 收集主线和次级主线的行业名集合
        const allIndNames = new Set();
        [...main, ...sub].forEach(g => { if (g.industry) allIndNames.add(g.industry); });
        const otherCount = getTrackedCount() - sumTrackedInIndustries(allIndNames);
        const showOther = otherCount > 0;

        // 主Tab
        let tabsHtml =
            `<div class="main-tab ${activeMain === 'main' ? 'active' : ''}" onclick="switchMain('main')">📈 主线 (${sumCnt(main)})</div>` +
            `<div class="main-tab ${activeMain === 'sub' ? 'active' : ''}" onclick="switchMain('sub')">📊 次级主线 (${sumCnt(sub)})</div>`;
        if (showOther) tabsHtml += `<div class="main-tab ${activeMain === 'other' ? 'active' : ''}" onclick="switchMain('other')">🗂 其他 (${otherCount})</div>`;
        tabsHtml += `<div class="main-tab ${activeMain === 'tracked' ? 'active' : ''}" onclick="switchMain('tracked')">✅ 已跟踪 (${getTrackedCount()})</div>`;
        document.getElementById('mainTabs').innerHTML = tabsHtml;
        const groups = getGroups().filter(g => g.candidates && g.candidates.length > 0);
        if (groups.length === 0) {
            document.getElementById('indTabs').innerHTML = '';
            document.getElementById('cardsArea').innerHTML = '<div class="empty">该分类下暂无候选</div>';
            document.getElementById('pagination').innerHTML = '';
            return;
        }

        // 默认选中第一个行业
        if (!activeInd || !groups.some(g => g.industry === activeInd)) activeInd = groups[0].industry;

        // 行业Tab
        document.getElementById('indTabs').innerHTML = groups.map(g =>
            `<div class="ind-tab ${g.industry === activeInd ? 'active' : ''}" onclick="switchInd('${g.industry}')">${g.industry} <span class="count">(${g.candidates.length})</span></div>`
        ).join('');

        // 当前行业股票
        const grp = groups.find(g => g.industry === activeInd);
        if (!grp) return;

        const items = grp.candidates;
        const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
        if (curPage > totalPages) curPage = totalPages;
        const start = (curPage - 1) * PAGE_SIZE;
        const pageItems = items.slice(start, start + PAGE_SIZE);

        let html = '';
        pageItems.forEach((s, i) => {
            // 强制使用趋势交易的图表前缀和BIAS信息
            const sd = Object.assign({}, s, {
                trading_system: 'trend',
            });
            const checked = s.in_manual ? 'checked' : '';
            const card = signalStockCard(sd, start + i + 1);
            // 替换图表ID避免冲突
            const cardHtml = card.replace(/id="hchart_/g, `id="tc_${activeInd}_`)
                       .replace(/toggleChart\('hchart_/g, "toggleChart('tc_" + activeInd + "_");
            // 卡片+勾选框并排
            html += `<div style="display:flex;align-items:stretch;gap:0;margin-bottom:6px;">
                <div style="flex:1;">${cardHtml}</div>
                <div style="display:flex;align-items:center;padding:0 8px;border-left:1px solid #1a1a30;">
                    <input type="checkbox" ${checked} onchange="toggleStock('${s.code}', this.checked)" style="accent-color:#4ecdc4;width:18px;height:18px;cursor:pointer;">
                </div>
            </div>`;
        });

        document.getElementById('cardsArea').innerHTML = html ||
            '<div class="empty">暂无候选</div>';

        // 分页
        document.getElementById('pagination').innerHTML = totalPages > 1
            ? `<div class="pagination">
                <div class="page-btn ${curPage <= 1 ? 'disabled' : ''}" onclick="${curPage > 1 ? "goPage("+(curPage-1)+")" : ''}">◀ 上一页</div>
                <span class="page-info">${curPage}/${totalPages}</span>
                <div class="page-btn ${curPage >= totalPages ? 'disabled' : ''}" onclick="${curPage < totalPages ? "goPage("+(curPage+1)+")" : ''}">下一页 ▶</div>
               </div>`
            : '';
    }

    function getGroups() {
        if (activeMain === 'tracked') {
            const tracked = rawData._tracked?.candidates || [];
            return tracked.length > 0 ? [{industry: '已跟踪', candidates: tracked}] : [];
        }
        if (activeMain === 'other') {
            // 已跟踪但行业不在当前主线/次级主线的
            const allIndNames = new Set();
            [...(rawData.main_lines||[]), ...(rawData.sub_main_lines||[])].forEach(g => {
                if (g.industry) allIndNames.add(g.industry);
            });
            const other = (rawData._tracked?.candidates || []).filter(c => !allIndNames.has(c.sector));
            return other.length > 0 ? [{industry: '其他', candidates: other}] : [];
        }
        return activeMain === 'main' ? (rawData.main_lines || []) : (rawData.sub_main_lines || []);
    }

    function getTrackedCount() {
        return rawData._tracked?.count || 0;
    }

    function sumTrackedInIndustries(indSet) {
        return (rawData._tracked?.candidates || []).filter(c => indSet.has(c.sector)).length;
    }

    function switchMain(t) { activeMain = t; activeInd = null; curPage = 1; render(); }
    function switchInd(ind) { activeInd = ind; curPage = 1; render(); }
    function goPage(p) { curPage = p; render(); }
    function sumCnt(groups) { return groups.reduce((s, g) => s + (g.candidates ? g.candidates.length : 0), 0); }

    // 打勾/取消勾
    window.toggleStock = async function(code, enable) {
        try {
            const r = await fetch('/api/trend-candidates/toggle?code=' + code + '&enable=' + enable);
            const d = await r.json();
            if (d.success) {
                showToast(enable ? `✅ ${code} 已加入趋势交易` : `❌ ${code} 已移除`);
                // 刷新全部数据
                const [r2, r3] = await Promise.all([
                    fetch('/api/trend-candidates'),
                    fetch('/api/trend-tracked')
                ]);
                rawData = await r2.json();
                rawData._tracked = await r3.json();
                render();
            }
        } catch(e) {
            showToast('⚠️ 操作失败');
        }
    };

    loadData();