/**
 * 共享导航栏 — 全局统一
 * 所有页面通过 <script src="/nav.js"></script> 引用
 * 自动生成顶部导航 + 底部导航，高亮当前页
 */
(function() {
    const MAIN_NAV = [
        { label: '📡 盘中盯盘',  href: '/monitor.html',         id: 'monitor' },
        { label: '📋 每日复盘',  href: '/review.html',          id: 'review' },
        { label: '🧑 工作台',    href: '/journal.html',          id: 'workbench' },
        { label: '📋 自选股',    href: '/watchlist.html',        id: 'watchlist' },
        { label: '🔍 个股分析',  href: '/stock_analysis.html',   id: 'stock_analysis' },
        { label: '🎯 趋势候选',  href: '/trend_candidates.html', id: 'trend' },
        { label: '🔬 行业追踪',  href: '/industry.html',        id: 'industry' },
        { label: '📈 涨幅榜',    href: '/top_gainers.html',     id: 'gainers' },
        { label: '🌍 宏观环境',  href: '/macro.html',           id: 'macro' },
        { label: '📝 交易技巧',  href: '/tips.html',            id: 'tips' },
    ];

    const FOOTER_LINKS = [
        { label: '📋 每日成果',    href: '/index.html',             id: 'home' },
        { label: '📖 Skills',    href: '/skills.html',            id: 'skills' },
        { label: '📊 模拟交易',  href: '/simulation.html',       id: 'simulation' },
    ];

    const path = window.location.pathname;
    let currentId = null;
    if (path.startsWith('/archive/')) {
        currentId = null;
    } else {
        currentId = 'monitor';
        for (const item of MAIN_NAV) {
            if (path.startsWith(item.href)) {
                currentId = item.id;
                break;
            }
        }
    }

    function buildTopNav() {
        const topColors = {
            monitor: '#4ecdc4', review: '#e94560', workbench: '#f59e0b',
            watchlist: '#22c55e', stock_analysis: '#e94560',
            trend: '#4ecdc4', industry: '#22c55e', gainers: '#e94560',
            macro: '#2196f3', tips: '#f59e0b',
        };
        return MAIN_NAV.map(item => {
            const isCurrent = item.id === currentId;
            const color = isCurrent ? '#e94560' : (topColors[item.id] || '#e67e22');
            const weight = isCurrent ? 'font-weight:bold;' : '';
            const tag = isCurrent ? 'span' : 'a';
            const extra = isCurrent ? '' : ` href="${item.href}"`;
            return `<${tag}${extra} style="color:${color};text-decoration:none;font-size:12px;${weight}">${item.label}</${tag}>`;
        }).join('<span class="nav-sep" style="color:#333;margin:0 6px;">|</span>');
    }

    function buildBottomNav() {
        let html = MAIN_NAV.map(item => {
            const isCurrent = item.id === currentId;
            const color = isCurrent ? '#e94560' : '#4ecdc4';
            const tag = isCurrent ? 'span' : 'a';
            const extra = isCurrent ? '' : ` href="${item.href}"`;
            return `<${tag}${extra} style="color:${color};text-decoration:none;font-size:13px;${isCurrent?'font-weight:bold;':''}">${item.label}</${tag}>`;
        }).join('<span class="nav-sep" style="color:#333;margin:0 6px;">|</span>');
        html += '<br><span style="color:#555;font-size:11px;">';
        html += FOOTER_LINKS.map(item => {
            const tag = 'a';
            return `<${tag} href="${item.href}" style="color:#555;text-decoration:none;font-size:11px;">${item.label}</${tag}>`;
        }).join('<span style="color:#444;margin:0 4px;">·</span>');
        html += '</span>';
        return html;
    }

    const topNav = document.getElementById('nav-top');
    if (topNav) {
        topNav.innerHTML = buildTopNav();
        topNav.style.display = 'flex';
        topNav.style.gap = '10px';
        topNav.style.justifyContent = 'center';
        topNav.style.marginTop = '10px';
        topNav.style.flexWrap = 'wrap';
    }

    const bottomNav = document.getElementById('nav-bottom');
    if (bottomNav) {
        bottomNav.innerHTML = buildBottomNav();
        bottomNav.style.display = 'flex';
        bottomNav.style.flexDirection = 'column';
        bottomNav.style.alignItems = 'center';
        bottomNav.style.gap = '12px';
        bottomNav.style.margin = '20px 0';
        bottomNav.style.flexWrap = 'wrap';
    }
})();
