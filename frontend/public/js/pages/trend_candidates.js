/**
 * 趋势候选管理 v5
 * 
 * 布局：[搜索框] + [自动候选 | 已跟踪] Tab
 * - 自动候选：主线+次主线合并显示，按行业分组
 * - 已跟踪：所有手动标记的趋势股
 * - 搜索框：从自选股中搜索，点击即加入已跟踪
 */
const PAGE_SIZE = 10;
let rawData = null;
let activeMain = 'auto';  // 'auto' | 'tracked'
let activeInd = null;
let curPage = 1;
let searchTimer = null;

const toast = document.getElementById('toast');
function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2000);
}

// ── 加载数据 ──
async function loadData() {
    try {
        const [r1, r2, r3] = await Promise.all([
            fetch('/api/trend-candidates'),
            fetch('/api/trend-tracked'),
            fetch('/api/watchlist'),    // 加载自选股，供搜索用
        ]);
        const candidates = await r1.json();
        const tracked = await r2.json();
        const wl = await r3.json();
        rawData = { candidates, tracked, watchlist: wl.stocks || [] };
        render();
    } catch (e) {
        document.getElementById('cardsArea').innerHTML = '<div class="empty">❌ 加载失败</div>';
    }
}

// ── 渲染 ──
function render() {
    if (!rawData) return;

    const auto = getAutoCandidates();
    const tracked = rawData.tracked?.candidates || [];
    const autoCount = auto.reduce((s, g) => s + (g.candidates ? g.candidates.length : 0), 0);
    const trackedCount = rawData.tracked?.count || 0;

    document.getElementById('stats').innerHTML =
        `自动候选 <b>${autoCount}</b> 只 · 已跟踪 <b>${trackedCount}</b> 只`;

    // 主Tab
    document.getElementById('mainTabs').innerHTML =
        `<div class="main-tab ${activeMain === 'auto' ? 'active' : ''}" onclick="switchMain('auto')">📈 自动候选 (${autoCount})</div>` +
        `<div class="main-tab ${activeMain === 'tracked' ? 'active' : ''}" onclick="switchMain('tracked')">✅ 已跟踪 (${trackedCount})</div>`;

    if (activeMain === 'tracked') {
        renderTracked(tracked);
        return;
    }

    renderAuto(auto);
}

// ── 自动候选渲染 ──
function renderAuto(groups) {
    groups = groups.filter(g => g.candidates && g.candidates.length > 0);
    if (groups.length === 0) {
        document.getElementById('indTabsWrap').innerHTML = '';
        document.getElementById('cardsArea').innerHTML = '<div class="empty">暂无自动候选</div>';
        document.getElementById('pagination').innerHTML = '';
        return;
    }

    // 默认选中第一个行业
    if (!activeInd || !groups.some(g => g.industry === activeInd)) activeInd = groups[0].industry;

    // 行业Tab
    document.getElementById('indTabsWrap').innerHTML = groups.map(g =>
        `<div class="ind-tab ${g.industry === activeInd ? 'active' : ''}" onclick="switchInd('${g.industry}')">${g.industry} <span class="count">(${g.candidates.length})</span></div>`
    ).join('');

    const grp = groups.find(g => g.industry === activeInd);
    if (!grp) return;
    renderCandidates(grp.candidates);
}

// ── 已跟踪渲染 ──
function renderTracked(tracked) {
    document.getElementById('indTabsWrap').innerHTML = '';
    if (!tracked || tracked.length === 0) {
        document.getElementById('cardsArea').innerHTML = '<div class="empty">✅ 暂无已跟踪趋势股<br>在「自动候选」中打勾或使用搜索框添加</div>';
        document.getElementById('pagination').innerHTML = '';
        return;
    }
    renderCandidates(tracked);
}

// ── 通用候选卡片渲染 ──
function renderCandidates(items) {
    const totalPages = Math.max(1, Math.ceil(items.length / PAGE_SIZE));
    if (curPage > totalPages) curPage = totalPages;
    const start = (curPage - 1) * PAGE_SIZE;
    const pageItems = items.slice(start, start + PAGE_SIZE);

    const indPrefix = activeInd || 'tracked';
    let html = '';
    pageItems.forEach((s, i) => {
        const sd = Object.assign({}, s, { trading_system: 'trend' });
        const checked = s.in_manual ? 'checked' : '';
        const card = signalStockCard(sd, start + i + 1);
        const cardHtml = card.replace(/id="hchart_/g, `id="tc_${indPrefix}_`)
            .replace(/toggleChart\('hchart_/g, "toggleChart('tc_" + indPrefix + "_");
        html += `<div style="display:flex;align-items:stretch;gap:0;margin-bottom:6px;">
            <div style="flex:1;">${cardHtml}</div>
            <div style="display:flex;align-items:center;padding:0 8px;border-left:1px solid #1a1a30;">
                <input type="checkbox" ${checked} onchange="toggleStock('${s.code}', this.checked)" style="accent-color:#4ecdc4;width:18px;height:18px;cursor:pointer;">
            </div>
        </div>`;
    });

    document.getElementById('cardsArea').innerHTML = html ||
        '<div class="empty">暂无数据</div>';

    document.getElementById('pagination').innerHTML = totalPages > 1
        ? `<div class="pagination">
            <div class="page-btn ${curPage <= 1 ? 'disabled' : ''}" onclick="${curPage > 1 ? "goPage("+(curPage-1)+")" : ''}">◀ 上一页</div>
            <span class="page-info">${curPage}/${totalPages}</span>
            <div class="page-btn ${curPage >= totalPages ? 'disabled' : ''}" onclick="${curPage < totalPages ? "goPage("+(curPage+1)+")" : ''}">下一页 ▶</div>
           </div>`
        : '';
}

// ── 数据获取 ──
function getAutoCandidates() {
    const main = rawData.candidates?.main_lines || [];
    const sub = rawData.candidates?.sub_main_lines || [];
    // 合并主线+次主线，同行业合并
    const merged = {};
    [...main, ...sub].forEach(g => {
        const ind = g.industry;
        if (!merged[ind]) merged[ind] = { industry: ind, candidates: [] };
        (g.candidates || []).forEach(c => {
            if (!merged[ind].candidates.some(x => x.code === c.code)) {
                merged[ind].candidates.push(c);
            }
        });
    });
    return Object.values(merged);
}

// ── 搜索框（客户端匹配，支持代码/名称/拼音首字母）──
let _wlCache = null;
function onSearchInput(val) {
    clearTimeout(searchTimer);
    const el = document.getElementById('searchResults');
    if (!val || val.length < 1) { el.style.display = 'none'; return; }
    searchTimer = setTimeout(async () => {
        try {
            // 获取手动趋势列表（用于标记 in_trend）
            let manualCodes = new Set();
            if (rawData?.tracked?.candidates) {
                manualCodes = new Set(rawData.tracked.candidates.map(c => c.code));
            }
            const wl = rawData?.watchlist || [];
            const q = val.trim().toLowerCase();

            // 客户端匹配：代码/名称/拼音首字母
            const results = wl.filter(s => {
                const code = (s.code || '').toLowerCase();
                const name = (s.name || '').toLowerCase();
                const py = getPinyinInitials(s.name || '').toLowerCase();
                return code.includes(q) || name.includes(q) || py.includes(q);
            });

            if (results.length === 0) {
                el.innerHTML = '<div class="search-result-item" style="color:#888;">无匹配自选股</div>';
                el.style.display = 'block';
                return;
            }
            el.innerHTML = results.slice(0, 20).map(st => {
                const inTrend = manualCodes.has(st.code);
                const label = inTrend ? '✅ 已加入' : '➕ 加入';
                const color = inTrend ? '#4ecdc4' : '#2196f3';
                return `<div class="search-result-item" onclick="addFromWatchlist('${st.code}', ${!inTrend})" style="cursor:pointer;">
                    <span><span class="sr-name">${st.name}</span> <span class="sr-code">${st.code}</span></span>
                    <span class="sr-ind">${st.direction || ''}</span>
                    <span style="float:right;color:${color};font-size:11px;">${label}</span>
                </div>`;
            }).join('');
            el.style.display = 'block';
        } catch (e) {
            el.style.display = 'none';
        }
    }, 300);
}

function hideSearchResults() {
    setTimeout(() => {
        const el = document.getElementById('searchResults');
        if (el) el.style.display = 'none';
    }, 200);
}

async function addFromWatchlist(code, enable) {
    try {
        const r = await fetch('/api/trend-candidates/toggle?code=' + code + '&enable=' + enable);
        const d = await r.json();
        if (d.success === false && d.error) { showToast('❌ ' + d.error); return; }
        if (enable) {
            showToast(`✅ ${code} 已加入趋势交易`);
        } else {
            showToast(`⚠️ ${code} 已在趋势交易中`);
        }
        document.getElementById('searchResults').style.display = 'none';
        document.getElementById('searchInput').value = '';
        // 刷新全部数据
        const [r1, r2] = await Promise.all([
            fetch('/api/trend-candidates'),
            fetch('/api/trend-tracked'),
        ]);
        rawData = { candidates: await r1.json(), tracked: await r2.json() };
        render();
    } catch (e) {
        showToast('❌ 操作失败');
    }
}

// ── 打勾/取消勾 ──
window.toggleStock = async function (code, enable) {
    try {
        const r = await fetch('/api/trend-candidates/toggle?code=' + code + '&enable=' + enable);
        const d = await r.json();
        if (d.success === false && d.error) { showToast('❌ ' + d.error); return; }
        showToast(enable ? `✅ ${code} 已加入趋势交易` : `❌ ${code} 已移除`);
        // 刷新全部数据
        const [r1, r2] = await Promise.all([
            fetch('/api/trend-candidates'),
            fetch('/api/trend-tracked'),
        ]);
        rawData = { candidates: await r1.json(), tracked: await r2.json() };
        render();
    } catch (e) {
        showToast('❌ 操作失败');
    }
};

// ── Tab切换 ──
function switchMain(t) {
    activeMain = t;
    activeInd = null;
    curPage = 1;
    render();
}

function switchInd(ind) {
    activeInd = ind;
    curPage = 1;
    render();
}

function goPage(p) {
    curPage = p;
    render();
}

// ── 启动 ──
loadData();
