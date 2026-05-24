/**
 * 共享导航栏 — 全局统一
 * 所有页面通过 <script src="/nav.js"></script> 引用
 * 自动生成顶部导航 + 底部导航，高亮当前页
 */
(function() {
    const NAV_ITEMS = [
        { label: '🏠 成果跟踪',  href: '/',                     id: 'home' },
        { label: '📋 每日复盘',  href: '/review.html',          id: 'review' },
        { label: '📡 盘中盯盘',  href: '/monitor.html',         id: 'monitor' },
        { label: '🌍 宏观环境',  href: '/macro.html',           id: 'macro' },
        { label: '📈 涨幅榜',    href: '/top_gainers.html',     id: 'gainers' },
        { label: '🔬 行业追踪',  href: '/industry.html',        id: 'industry' },
        { label: '🎯 趋势候选',  href: '/trend_candidates.html', id: 'trend_candidates' },
        { label: '📝 交易技巧',  href: '/tips.html',            id: 'tips' },
        { label: '📖 Skills',    href: '/skills.html',           id: 'skills' },
        { label: '📊 模拟交易',  href: '/simulation.html',       id: 'simulation' },
        { label: '📋 自选股',    href: '/watchlist.html',        id: 'watchlist' },
        { label: '📋 交易日志',  href: '/journal.html',          id: 'journal' },
        { label: '🔍 个股分析',  href: '/stock_analysis.html',   id: 'stock_analysis' },
    ];

    const path = window.location.pathname;
    let currentId = null;
    if (path.startsWith('/archive/')) {
        currentId = null;
    } else {
        currentId = 'home';
        for (const item of NAV_ITEMS) {
            if (item.href !== '/' && path.startsWith(item.href)) {
                currentId = item.id;
                break;
            }
        }
    }

    function buildNavHTML(containerClass) {
        const topColors = {
            home: '#4ecdc4', review: '#e94560', macro: '#2196f3', gainers: '#e94560',
            industry: '#22c55e', trend_candidates: '#4ecdc4', tips: '#f59e0b',
            skills: '#a855f7', simulation: '#e94560', watchlist: '#22c55e',
            journal: '#f59e0b', stock_analysis: '#e94560',
        };
        return NAV_ITEMS.map(item => {
            const isCurrent = item.id === currentId;
            if (containerClass === 'nav-top') {
                const color = isCurrent ? '#e94560' : (topColors[item.id] || '#e67e22');
                const weight = isCurrent ? 'font-weight:bold;' : '';
                const tag = isCurrent ? 'span' : 'a';
                const extra = isCurrent ? '' : ` href="${item.href}"`;
                return `<${tag}${extra} style="color:${color};text-decoration:none;font-size:12px;${weight}">${item.label}</${tag}>`;
            } else {
                const color = isCurrent ? '#e94560' : '#4ecdc4';
                const tag = isCurrent ? 'span' : 'a';
                const extra = isCurrent ? '' : ` href="${item.href}"`;
                return `<${tag}${extra} style="color:${color};text-decoration:none;font-size:13px;${isCurrent?'font-weight:bold;':''}">${item.label}</${tag}>`;
            }
        }).join('<span class="nav-sep" style="color:#333;margin:0 6px;">|</span>');
    }

    const topNav = document.getElementById('nav-top');
    if (topNav) {
        topNav.innerHTML = buildNavHTML('nav-top');
        topNav.style.display = 'flex';
        topNav.style.gap = '10px';
        topNav.style.justifyContent = 'center';
        topNav.style.marginTop = '10px';
        topNav.style.flexWrap = 'wrap';
    }

    const bottomNav = document.getElementById('nav-bottom');
    if (bottomNav) {
        bottomNav.innerHTML = buildNavHTML('nav-bottom');
        bottomNav.style.display = 'flex';
        bottomNav.style.gap = '12px';
        bottomNav.style.justifyContent = 'center';
        bottomNav.style.margin = '20px 0';
        bottomNav.style.flexWrap = 'wrap';
    }
})();
