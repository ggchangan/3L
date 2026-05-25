/**
 * 交易工作台 — JS 逻辑
 * 6区块：复盘摘要 → 待办 → 计划 → 操作 → 执行复盘 → 反思
 */
let wbDate = new Date().toISOString().slice(0, 10);
let wbData = null;
let currentDateIndex = 0;
let allDates = [];

async function init() {
    // 加载复盘摘要
    try {
        const r = await fetch('/api/review/get');
        const review = await r.json();
        document.getElementById('rsMarket').textContent = review.market?.structure || '--';
        document.getElementById('rsMainline').textContent = review.mainline?.primary || '--';
        document.getElementById('rsSignals').textContent = review.timing_signals?.length || 0;
    } catch(e) { /* no review data yet */ }

    // 加载日志列表
    try {
        const r = await fetch('/api/workbench/list');
        const data = await r.json();
        allDates = data.dates || [];
        currentDateIndex = allDates.indexOf(wbDate);
    } catch(e) {}

    await loadLog(wbDate);
}

async function loadLog(date) {
    wbDate = date;
    document.getElementById('wbDate').textContent = date;

    try {
        const r = await fetch('/api/workbench/get?date=' + date);
        wbData = await r.json();
    } catch(e) {
        showToast('❌ 加载失败', true);
        return;
    }

    renderTodos();
    renderPlans();
    document.getElementById('opText').value = wbData.operations || '';
    document.getElementById('execReviewText').value = wbData.execution_review || '';
    document.getElementById('refDiscipline').value = wbData.reflection?.discipline || '';
    document.getElementById('refRating').value = wbData.reflection?.rating || '';
    document.getElementById('refLearned').value = wbData.reflection?.learned || '';

    // 加载昨日计划（执行复盘用）
    loadYesterdayPlan();
}

function loadYesterdayPlan() {
    const prevDate = new Date(wbDate);
    prevDate.setDate(prevDate.getDate() - 1);
    const prevStr = prevDate.toISOString().slice(0, 10);

    fetch('/api/workbench/get?date=' + prevStr)
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById('yesterdayPlan');
            const plan = data.plan || {};
            const hasBuy = (plan.buy || []).length > 0;
            const hasSell = (plan.sell || []).length > 0;
            const hasWatch = (plan.watch || []).length > 0;

            if (!hasBuy && !hasSell && !hasWatch) {
                el.innerHTML = '<div style="font-size:11px;color:#555;">昨日无计划</div>';
                return;
            }

            let html = '<div style="font-size:11px;color:#888;margin-bottom:4px;">📋 昨日计划（' + prevStr + '）</div>';
            if (hasBuy) {
                html += '<div style="font-size:11px;">🟢 买入：';
                html += (plan.buy || []).map(p =>
                    '<span style="color:#e0e0e0;">' + (p.stock || '--') + '</span>(' + (p.condition || '') + ')'
                ).join('、');
                html += '</div>';
            }
            if (hasSell) {
                html += '<div style="font-size:11px;">🔴 卖出：';
                html += (plan.sell || []).map(p =>
                    '<span style="color:#e0e0e0;">' + (p.stock || '--') + '</span>(' + (p.condition || '') + ')'
                ).join('、');
                html += '</div>';
            }
            if (hasWatch) {
                html += '<div style="font-size:11px;">👁️ 观察：';
                html += (plan.watch || []).map(p =>
                    '<span style="color:#e0e0e0;">' + (p.stock || p.sector || '--') + '</span>→' + (p.focus || '')
                ).join('、');
                html += '</div>';
            }
            el.innerHTML = html;
        })
        .catch(() => {
            document.getElementById('yesterdayPlan').innerHTML = '<div style="font-size:11px;color:#555;">昨日无计划数据</div>';
        });
}

// ── 待办 ──
function renderTodos() {
    const el = document.getElementById('todoList');
    const todos = wbData.todos || [];
    if (todos.length === 0) {
        el.innerHTML = '<div style="font-size:11px;color:#555;">暂无待办，添加一个开始工作</div>';
        return;
    }
    el.innerHTML = todos.map((t, i) =>
        '<div class="todo-item' + (t.done ? ' done' : '') + '">' +
            '<input type="checkbox" ' + (t.done ? 'checked' : '') + ' onchange="toggleTodo(' + i + ')">' +
            '<label>' + t.text + '</label>' +
            '<span style="margin-left:auto;color:#e94560;cursor:pointer;font-size:11px;" onclick="removeTodo(' + i + ')">✕</span>' +
        '</div>'
    ).join('');
}

function addTodo() {
    const text = prompt('待办内容：');
    if (!text) return;
    if (!wbData.todos) wbData.todos = [];
    wbData.todos.push({text, done: false});
    renderTodos();
}

function toggleTodo(i) {
    wbData.todos[i].done = !wbData.todos[i].done;
    renderTodos();
}

function removeTodo(i) {
    wbData.todos.splice(i, 1);
    renderTodos();
}

// ── 计划 ──
function renderPlans() {
    const plan = wbData.plan || {buy: [], sell: [], watch: []};
    renderPlanRows('buy', plan.buy || []);
    renderPlanRows('sell', plan.sell || []);
    renderPlanRows('watch', plan.watch || []);
}

function renderPlanRows(type, items) {
    const el = document.getElementById('plan' + type.charAt(0).toUpperCase() + type.slice(1) + 'Rows');
    if (type === 'watch') {
        el.innerHTML = items.map((p, i) =>
            '<div class="plan-row">' +
                '<input value="' + (p.stock || p.sector || '') + '" placeholder="标的/板块" onchange="updatePlan(' + type + ',' + i + ',\'stock\',this.value)">' +
                '<input value="' + (p.focus || '') + '" placeholder="关注点" onchange="updatePlan(' + type + ',' + i + ',\'focus\',this.value)">' +
                '<span></span>' +
                '<select onchange="updatePlan(' + type + ',' + i + ',\'status\',this.value)">' +
                    '<option value="pending" ' + (p.status === 'pending' ? 'selected' : '') + '>⏳ 待触发</option>' +
                    '<option value="triggered" ' + (p.status === 'triggered' ? 'selected' : '') + '>⚡ 已触发</option>' +
                    '<option value="executed" ' + (p.status === 'executed' ? 'selected' : '') + '>✅ 已执行</option>' +
                    '<option value="not_triggered" ' + (p.status === 'not_triggered' ? 'selected' : '') + '>❌ 未触发</option>' +
                '</select>' +
                '<span style="color:#e94560;cursor:pointer;font-size:11px;" onclick="removePlan(' + type + ',' + i + ')">✕</span>' +
            '</div>'
        ).join('');
    } else {
        el.innerHTML = items.map((p, i) =>
            '<div class="plan-row">' +
                '<input value="' + (p.stock || '') + '" placeholder="代码/名称" onchange="updatePlan(' + type + ',' + i + ',\'stock\',this.value)">' +
                '<input value="' + (p.condition || '') + '" placeholder="条件" onchange="updatePlan(' + type + ',' + i + ',\'condition\',this.value)">' +
                '<input value="' + (p.qty || '') + '" placeholder="数量" onchange="updatePlan(' + type + ',' + i + ',\'qty\',this.value)">' +
                '<select onchange="updatePlan(' + type + ',' + i + ',\'status\',this.value)">' +
                    '<option value="pending" ' + (p.status === 'pending' ? 'selected' : '') + '>⏳ 待触发</option>' +
                    '<option value="triggered" ' + (p.status === 'triggered' ? 'selected' : '') + '>⚡ 已触发</option>' +
                    '<option value="executed" ' + (p.status === 'executed' ? 'selected' : '') + '>✅ 已执行</option>' +
                    '<option value="not_triggered" ' + (p.status === 'not_triggered' ? 'selected' : '') + '>❌ 未触发</option>' +
                '</select>' +
                '<span style="color:#e94560;cursor:pointer;font-size:11px;" onclick="removePlan(' + type + ',' + i + ')">✕</span>' +
            '</div>'
        ).join('');
    }
}

function addPlanRow(type) {
    if (!wbData.plan) wbData.plan = {buy: [], sell: [], watch: []};
    if (!wbData.plan[type]) wbData.plan[type] = [];
    wbData.plan[type].push({stock: '', condition: '', qty: '', status: 'pending'});
    renderPlans();
}

function updatePlan(type, i, field, value) {
    if (!wbData.plan || !wbData.plan[type] || !wbData.plan[type][i]) return;
    wbData.plan[type][i][field] = value;
}

function removePlan(type, i) {
    if (!wbData.plan || !wbData.plan[type]) return;
    wbData.plan[type].splice(i, 1);
    renderPlans();
}

// ── 日期导航 ──
function loadPrevDay() {
    const d = new Date(wbDate);
    d.setDate(d.getDate() - 1);
    loadLog(d.toISOString().slice(0, 10));
}

function loadNextDay() {
    const d = new Date(wbDate);
    d.setDate(d.getDate() + 1);
    loadLog(d.toISOString().slice(0, 10));
}

// ── 保存 ──
async function saveWorkbench() {
    if (!wbData) return;

    // 收集数据
    wbData.date = wbDate;
    wbData.operations = document.getElementById('opText').value;
    wbData.execution_review = document.getElementById('execReviewText').value;
    wbData.reflection = {
        discipline: document.getElementById('refDiscipline').value,
        rating: document.getElementById('refRating').value,
        learned: document.getElementById('refLearned').value,
    };

    try {
        const r = await fetch('/api/workbench/save', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(wbData),
        });
        const data = await r.json();
        if (data.success) {
            showToast('✅ 日志已保存');
        } else {
            showToast('⚠️ 保存失败: ' + (data.error || '未知错误'), true);
        }
    } catch(e) {
        showToast('⚠️ 保存失败: ' + e.message, true);
    }
}

// ── Toast ──
function showToast(msg, isError) {
    let el = document.getElementById('wbToast');
    if (!el) {
        el = document.createElement('div');
        el.id = 'wbToast';
        el.style.cssText = 'position:fixed;bottom:30px;left:50%;transform:translate(-50%);background:#1a1a2e;border:1px solid #22c55e;color:#22c55e;padding:8px 20px;border-radius:6px;font-size:13px;opacity:0;transition:opacity .3s;z-index:999';
        document.body.appendChild(el);
    }
    el.textContent = msg;
    el.style.borderColor = isError ? '#e94560' : '#22c55e';
    el.style.color = isError ? '#e94560' : '#22c55e';
    el.style.opacity = '1';
    setTimeout(() => { el.style.opacity = '0'; }, 2500);
}

document.addEventListener('DOMContentLoaded', init);
