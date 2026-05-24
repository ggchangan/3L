/**
 * 自选股管理 v4
 * 方向管理独立模块：API /api/directions/*
 */
let enrichedData = null;
let trendCodes = new Set();
let activeDir = '全部';
let searchTimer = null;
let dirData = null;  // {directions: {name: active}, active: [...], suggestions: {...}}

// ── Toast ──
const toast = document.getElementById('toast');
function showToast(msg, isErr) {
    toast.textContent = msg;
    toast.style.borderColor = isErr ? '#e94560' : '#22c55e';
    toast.style.color = isErr ? '#e94560' : '#22c55e';
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2000);
}

// ── 方向API ──
async function loadDirections() {
    try {
        const r = await fetch('/api/directions/get');
        const data = await r.json();
        dirData = data;
        return data;
    } catch(e) {
        dirData = {directions: {}, active: [], suggestions: {}};
        return dirData;
    }
}

function getActiveDirs() {
    return dirData ? (dirData.active || []) : [];
}

function isDirActive(name) {
    return dirData && dirData.active && dirData.active.includes(name);
}

// ── 加载数据 ──
async function loadData() {
    try {
        const [r1, r2, r3] = await Promise.all([
            fetch('/api/watchlist/analysis'),
            fetch('/api/trend-tracked'),
            loadDirections(),
        ]);
        enrichedData = await r1.json();
        const td = await r2.json();
        trendCodes = new Set((td.candidates || []).map(c => c.code));
        render();
    } catch(e) {
        document.getElementById('cardsArea').innerHTML = '<div class="empty">❌ 加载失败</div>';
    }
}

// ── 渲染 ──
function render() {
    if (!enrichedData) return;
    const stocks = enrichedData.stocks || [];
    const active = getActiveDirs();
    const tracked = stocks.filter(s => active.includes(s.direction || '其他'));
    document.getElementById('stats').innerHTML =
        `共 <b>${stocks.length}</b> 只 · 跟踪 <b>${tracked.length}</b> 只 · 趋势 ${trendCodes.size} 只`;
    renderDirTabs(stocks);
    renderCards();
    renderDirList();
    populateAddDirSelect();
}

// ── 方向Tab ──
function renderDirTabs(stocks) {
    const active = getActiveDirs();
    const counts = {'全部': stocks.length};
    active.forEach(d => counts[d] = 0);
    stocks.forEach(s => {
        const d = s.direction || '其他';
        if (active.includes(d)) counts[d] = (counts[d] || 0) + 1;
    });
    const tabs = [
        {name: '全部', label: `全部 (${stocks.length})`},
        ...active.map(d => ({name: d, label: `${d} (${counts[d]||0})`})),
    ];
    document.getElementById('dirTabs').innerHTML = tabs.map(t => {
        const a = t.name === activeDir ? ' active' : '';
        return `<div class="dir-tab${a}" onclick="switchDir('${t.name}')">${t.label}</div>`;
    }).join('');
}

function switchDir(d) {
    activeDir = d;
    renderCards();
    renderDirTabs(enrichedData.stocks || []);
}

// ── 卡片渲染 ──
function renderCards() {
    const stocks = enrichedData.stocks || [];
    const filter = document.getElementById('filterInput').value.trim().toLowerCase();
    const active = getActiveDirs();

    let filtered = stocks.filter(s => {
        if (filter && !s.code.includes(filter) && !(s.name||'').toLowerCase().includes(filter)) return false;
        if (activeDir === '全部') return true;
        const d = s.direction || '其他';
        return d === activeDir && active.includes(d);
    });

    const structOrder = {'上涨趋势': 0, '区间震荡': 1, '下降趋势': 2};
    filtered.sort((a, b) => {
        const aa = active.includes(a.direction || '其他') ? 0 : 10;
        const bb = active.includes(b.direction || '其他') ? 0 : 10;
        if (aa !== bb) return aa - bb;
        const sa = structOrder[a.structure] ?? 3;
        const sb = structOrder[b.structure] ?? 3;
        if (sa !== sb) return sa - sb;
        return 0;
    });

    if (filtered.length === 0) {
        document.getElementById('cardsArea').innerHTML = '<div class="empty">无匹配股票</div>';
        return;
    }

    // 阶段颜色映射（与 stock_card.js 保持一致）
    const stageColors = {
        '上行': '#4ecdc4', '加速': '#e94560', '缩量整理': '#ffd700', '滞涨': '#ff6b6b',
        '转弱': '#ff6b6b', '下行': '#666', '加速跌': '#e94560', '转强': '#4ecdc4',
        '区间底部': '#4ecdc4', '区间中段': '#ffd700', '区间顶部': '#e94560'
    };
    let html = '';
    filtered.forEach((s, i) => {
        const tracked = active.includes(s.direction || '其他');
        const leftColor = stageColors[s.stage] || '#888';
        const cardData = {
            name: s.name || s.code, code: s.code, price: s.price, change: s.change,
            signal: s.signal || 'hold', structure: s.structure || '--', stage: s.stage || '--',
            sector: s.sector || '--', direction: s.direction || '其他',
            trading_system: s.trading_system || '3l', trend_bias: s.trend_bias,
            buy_point: s.buy_point || '', profit_model1: s.profit_model1 || false,
            trend_stock: s.trend_stock || false, vol_analysis: s.vol_analysis || '',
        };
        html += `<div class="watchlist-card-wrapper" style="border-left:3px solid ${leftColor};">`;
        html += signalStockCard(cardData, 'wl_' + i);

        // 底部操作栏 — 在统一容器内
        let tag = '';
        if (!tracked) tag = '<span class="tag-untracked">未跟踪</span>';
        const dirOpts = active.map(d =>
            `<option value="${d}" ${s.direction === d ? 'selected' : ''}>${d}</option>`
        ).join('');
        html += `<div class="watchlist-card-actions">
            <div class="wca-left">${tag}
                <select class="dir-select" onchange="changeDir('${s.code}', this.value)" style="width:68px;">
                    ${dirOpts}
                </select>
            </div>
            <button class="btn btn-red btn-sm" onclick="removeStock('${s.code}')" style="cursor:pointer;">✕ 删除</button>
        </div>`;
        html += '</div>';
    });

    document.getElementById('cardsArea').innerHTML = html;
}

// ── 方向管理面板 ──
function toggleDirPanel() {
    const panel = document.getElementById('dirPanel');
    const toggle = document.getElementById('dirIconToggle');
    if (panel.style.display === 'none') {
        panel.style.display = 'block';
        toggle.textContent = '🎯 方向管理 ▾';
        renderDirList();
    } else {
        panel.style.display = 'none';
        toggle.textContent = '🎯 方向管理 ▸';
    }
}

function switchAddTab(tab) {
    document.getElementById('tabSingle').className = tab === 'single' ? 'add-tab active' : 'add-tab';
    document.getElementById('tabBoard').className = tab === 'board' ? 'add-tab active' : 'add-tab';
    document.getElementById('addSingle').style.display = tab === 'single' ? 'block' : 'none';
    document.getElementById('addBoard').style.display = tab === 'board' ? 'block' : 'none';
}

async function renderDirList() {
    const data = await loadDirections();
    const dirs = data.directions || {};
    const active = data.active || [];
    const el = document.getElementById('dirList');

    const entries = Object.entries(dirs);
    if (entries.length === 0) {
        el.innerHTML = '<div style="color:#888;padding:10px;text-align:center;font-size:13px;">暂无方向，点击上方添加</div>';
        return;
    }

    let html = '';
    for (const [name, enabled] of entries) {
        if (name === '其他') continue; // 其他是保留项，不显示
        const isActive = active.includes(name);
        html += `<div class="dir-item ${isActive ? '' : 'inactive'}">
            <div>
                <span class="dir-item-name">${name}</span>
                <span class="dir-item-count">${countByDir(name)} 只</span>
                ${isActive ? '' : '<span style="color:#e94560;font-size:11px;margin-left:6px;">未跟踪</span>'}
            </div>
            <div class="dir-item-actions">
                <button class="dir-toggle ${isActive ? 'on' : 'off'}" onclick="toggleDir('${name}', ${!isActive})">
                    ${isActive ? '✅ 启用' : '⛔ 禁用'}
                </button>
                <button class="btn btn-red btn-sm" onclick="removeDir('${name}')">✕</button>
            </div>
        </div>`;
    }
    el.innerHTML = html;
    renderSuggestions(data.suggestions || {});
}

function countByDir(name) {
    const stocks = (enrichedData && enrichedData.stocks) || [];
    return stocks.filter(s => (s.direction || '其他') === name).length;
}

function renderSuggestions(suggestions) {
    const el = document.getElementById('dirSuggestions');
    let tags = [];
    if (suggestions.industry) tags.push({label: '🏭', items: suggestions.industry.slice(0,8)});
    if (suggestions.custom) tags.push({label: '📊', items: suggestions.custom.slice(0,6)});
    const flat = tags.flatMap(g => g.items);
    if (flat.length === 0) { el.style.display = 'none'; return; }
    el.innerHTML = flat.map(s =>
        `<span class="dir-suggestion-tag" onclick="fillDirName('${s}')">${s}</span>`
    ).join('');
    el.style.display = 'flex';
}

function fillDirName(name) {
    document.getElementById('newDirName').value = name;
    document.getElementById('dirSuggestions').style.display = 'none';
}

function updateBoardDirLabel() {
    const dir = document.getElementById('boardDir').value;
    const allLabel = document.querySelector('.dir-sr-row:first-child span');
    if (allLabel) {
        allLabel.textContent = `全选（全部添加到方向「${dir || '待选'}」）`;
    }
}

async function onBoardSearch(val) {
    clearTimeout(window._boardSearchTimer);
    const el = document.getElementById('boardResults');
    if (!val || val.length < 1) { el.style.display = 'none'; return; }
    window._boardSearchTimer = setTimeout(async () => {
        try {
            const r = await fetch('/api/directions/stocks?q=' + encodeURIComponent(val));
            const data = await r.json();
            if (!data.stocks || data.stocks.length === 0) {
                el.innerHTML = '<div class="dir-sr-empty">无匹配股票</div>';
                el.style.display = 'block';
                return;
            }
            const targetDir = document.getElementById('boardDir').value;
            let html = `<div class="dir-sr-info">共 ${data.total} 只匹配，显示前 ${data.stocks.length} 只</div>
                <label class="dir-sr-row" style="font-weight:bold;border-bottom:1px solid #2a2a4e;">
                    <input type="checkbox" onchange="toggleAllDirResults(this.checked)" checked>
                    <span>全选（全部添加到方向「${targetDir || '待选'}」）</span>
                </label>`;
            data.stocks.forEach(s => {
                const pct = s.change_pct || 0;
                const color = pct >= 0 ? '#ff4444' : '#22c55e';
                const sign = pct >= 0 ? '+' : '';
                html += `<label class="dir-sr-row">
                    <input type="checkbox" class="dir-sr-cb" data-code="${s.code}" data-name="${s.name}" data-direction="${s.direction}" checked>
                    <span class="dir-sr-code">${s.code}</span>
                    <span class="dir-sr-name">${s.name}</span>
                    <span class="dir-sr-ind">${s.industry||''}</span>
                    <span class="dir-sr-pct" style="color:${color}">${sign}${pct.toFixed(2)}%</span>
                </label>`;
            });
            html += `<button class="btn btn-green btn-sm" onclick="batchAddDirStocks()" style="margin:8px 0;width:100%;">✅ 批量添加已勾选股票</button>`;
            el.innerHTML = html;
            el.style.display = 'block';
        } catch(e) {
            el.innerHTML = '<div class="dir-sr-empty">❌ 搜索失败</div>';
            el.style.display = 'block';
        }
    }, 400);
}

function toggleAllDirResults(checked) {
    document.querySelectorAll('.dir-sr-cb').forEach(cb => cb.checked = checked);
}

async function batchAddDirStocks() {
    const targetDir = document.getElementById('boardDir').value;
    if (!targetDir) { showToast('⚠️ 请先选择方向', true); return; }

    const cbs = document.querySelectorAll('.dir-sr-cb:checked');
    if (cbs.length === 0) { showToast('⚠️ 请至少勾选一只股票', true); return; }

    const existing = new Set((enrichedData.stocks || []).map(s => s.code));
    const toAdd = [];

    cbs.forEach(cb => {
        const code = cb.dataset.code;
        if (!existing.has(code)) {
            toAdd.push({code, name: cb.dataset.name, direction: targetDir});
        }
    });

    if (toAdd.length === 0) { showToast('⚠️ 勾选的股票已在自选股中', true); return; }

    // 获取行业信息
    for (const s of toAdd) {
        try {
            const r = await fetch('/api/watchlist/search?q=' + s.code);
            const data = await r.json();
            if (data.results && data.results[0]) s.industry = data.results[0].industry || '';
        } catch(e) {}
    }

    const newStocks = [
        ...(enrichedData.stocks || []).map(s => ({code: s.code, name: s.name, direction: s.direction, industry: s.industry || ''})),
        ...toAdd,
    ];

    try {
        const r = await fetch('/api/watchlist/save', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({stocks: newStocks, count: newStocks.length}),
        });
        const data = await r.json();
        if (data.success) {
            showToast(`✅ 已添加 ${toAdd.length} 只股票`);
            const ra = await fetch('/api/watchlist/analysis');
            enrichedData = await ra.json();
            render();
        } else { showToast('⚠️ 保存失败', true); }
    } catch(e) { showToast('⚠️ 保存失败: ' + e.message, true); }
}

function showDirSuggestions(val) {
    const el = document.getElementById('dirSuggestions');
    if (!val) { el.style.display = 'none'; return; }
    // Suggestions already loaded via renderSuggestions, just keep visible
}

async function addDirection() {
    const input = document.getElementById('newDirName');
    const name = input.value.trim();
    if (!name) { showToast('⚠️ 请输入方向名称', true); return; }

    try {
        const r = await fetch('/api/directions/add', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name}),
        });
        const data = await r.json();
        if (data.success) {
            showToast(`✅ 已添加 "${name}"`);
            input.value = '';
            document.getElementById('dirSuggestions').style.display = 'none';
            await loadDirections();
            renderDirList();
            render();
        } else {
            showToast('⚠️ ' + (data.error || '添加失败'), true);
        }
    } catch(e) { showToast('⚠️ 添加失败', true); }
}

async function toggleDir(name, active) {
    try {
        const r = await fetch('/api/directions/toggle', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name, active}),
        });
        const data = await r.json();
        if (data.success) {
            showToast(active ? `✅ 已启用 "${name}"` : `⛔ 已禁用 "${name}"`);
            await loadDirections();
            renderDirList();
            render();
        } else { showToast('⚠️ ' + (data.error || '操作失败'), true); }
    } catch(e) { showToast('⚠️ 操作失败', true); }
}

async function removeDir(name) {
    if (!confirm(`确认删除方向 "${name}"？该方向股票将归入"其他"`)) return;
    try {
        const r = await fetch('/api/directions/remove', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name}),
        });
        const data = await r.json();
        if (data.success) {
            showToast(`❌ 已删除 "${name}"`);
            await loadDirections();
            renderDirList();
            render();
        } else { showToast('⚠️ ' + (data.error || '删除失败'), true); }
    } catch(e) { showToast('⚠️ 删除失败', true); }
}

// ── 添加自选股 ──
function populateAddDirSelect() {
    const sel = document.getElementById('addDir');
    const boardSel = document.getElementById('boardDir');
    const active = getActiveDirs();
    const opts = active.map(d => `<option value="${d}">${d}</option>`).join('');
    // 保留当前选中值
    const prevAdd = sel.value;
    sel.innerHTML = opts || '<option value="">先建方向</option>';
    if (prevAdd && [...sel.options].some(o => o.value === prevAdd)) sel.value = prevAdd;
    if (boardSel) {
        const prevBoard = boardSel.value;
        boardSel.innerHTML = opts || '<option value="">先建方向</option>';
        if (prevBoard && [...boardSel.options].some(o => o.value === prevBoard)) boardSel.value = prevBoard;
    }
}

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
                el.style.display = 'block'; return;
            }
            const active = getActiveDirs();
            const defaultDir = active.length > 0 ? active[0] : '其他';
            el.innerHTML = data.results.map(st =>
                `<div class="search-result-item" onclick="selectSearchResult('${st.code}','${st.name}','${defaultDir}')">
                    <span><span class="sr-name">${st.name}</span> <span class="sr-code">${st.code}</span></span>
                    <span class="sr-ind">${st.industry||''} · ${st.direction||'其他'}</span>
                </div>`
            ).join('');
            el.style.display = 'block';
        } catch(e) { el.style.display = 'none'; }
    }, 300);
}

function selectSearchResult(code, name, dir) {
    document.getElementById('addSearch').value = code + ' ' + name;
    document.getElementById('addSearch').dataset.selectedCode = code;
    document.getElementById('addSearch').dataset.selectedName = name;
    document.getElementById('searchResults').style.display = 'none';
}

async function addStock() {
    const input = document.getElementById('addSearch');
    const code = input.dataset.selectedCode;
    const name = input.dataset.selectedName;
    if (!code) { showToast('⚠️ 请先搜索选择股票', true); return; }
    const dir = document.getElementById('addDir').value;
    if (!dir) { showToast('⚠️ 请先创建方向', true); return; }

    if ((enrichedData.stocks || []).some(s => s.code === code)) {
        showToast(`⚠️ ${name}(${code}) 已在自选股中`, true);
        return;
    }

    let industry = '';
    try {
        const r = await fetch('/api/watchlist/search?q=' + code);
        const data = await r.json();
        if (data.results && data.results[0]) industry = data.results[0].industry || '';
    } catch(e) {}

    try {
        const r = await fetch('/api/watchlist/save', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                stocks: [...(enrichedData.stocks || []), {code, name, direction: dir, industry}],
                count: (enrichedData.stocks || []).length + 1,
            }),
        });
        const data = await r.json();
        if (data.success) {
            showToast(`✅ 已添加 ${name}(${code})`);
            input.value = '';
            delete input.dataset.selectedCode;
            delete input.dataset.selectedName;
            document.getElementById('searchResults').style.display = 'none';
            const ra = await fetch('/api/watchlist/analysis');
            enrichedData = await ra.json();
            render();
        } else { showToast('⚠️ 添加失败', true); }
    } catch(e) { showToast('⚠️ 添加失败: ' + e.message, true); }
}

async function changeDir(code, newDir) {
    const s = (enrichedData.stocks || []).find(x => x.code === code);
    if (s) {
        s.direction = newDir;
        await saveWatchlist();
        showToast(`✅ ${s.name||code} → ${newDir}`);
        render();
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
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({stocks, count: stocks.length}),
        });
        const data = await r.json();
        if (!data.success) showToast('⚠️ 保存失败', true);
    } catch(e) { showToast('⚠️ 保存失败: ' + e.message, true); }
}

// ── 启动 ──
loadData();
