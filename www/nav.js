/**
 * 共享导航栏 — 全局统一
 * 所有页面通过 <script src="/nav.js"></script> 引用
 * 自动生成顶部导航 + 底部导航，高亮当前页
 */
(function() {
    const NAV_ITEMS = [
        { label: '🏠 成果跟踪',  href: '/',              id: 'home' },
        { label: '📋 每日复盘',  href: '/review.html',    id: 'review' },
        { label: '📖 Skills',    href: '/skills.html',    id: 'skills' },
        { label: '📊 模拟交易',  href: '/simulation.html', id: 'simulation' },
    ];

    // 判断当前页面
    const path = window.location.pathname;
    let currentId = 'home';
    for (const item of NAV_ITEMS) {
        if (item.href !== '/' && path.startsWith(item.href)) {
            currentId = item.id;
            break;
        }
    }

    function buildNavHTML(containerClass) {
        return NAV_ITEMS.map(item => {
            const isCurrent = item.id === currentId;
            if (containerClass === 'nav-top') {
                const color = isCurrent ? '#e94560' : (item.id === 'home' ? '#4ecdc4' : item.id === 'review' ? '#e94560' : item.id === 'skills' ? '#a855f7' : '#e67e22');
                const weight = isCurrent ? 'font-weight:bold;' : '';
                return isCurrent
                    ? `<span style="color:${color};font-size:12px;${weight}">${item.label}</span>`
                    : `<a href="${item.href}" style="color:${color};text-decoration:none;font-size:12px;${weight}">${item.label}</a>`;
            } else {
                // 底部导航 — 简洁风格
                const color = isCurrent ? '#e94560' : '#4ecdc4';
                return isCurrent
                    ? `<span style="color:${color};font-size:13px;font-weight:bold;">${item.label}</span>`
                    : `<a href="${item.href}" style="color:${color};text-decoration:none;font-size:13px;">${item.label}</a>`;
            }
        }).join('<span class="nav-sep" style="color:#333;margin:0 6px;">|</span>');
    }

    // 插入顶部导航
    const topNav = document.getElementById('nav-top');
    if (topNav) {
        topNav.innerHTML = buildNavHTML('nav-top');
        topNav.style.display = 'flex';
        topNav.style.gap = '10px';
        topNav.style.justifyContent = 'center';
        topNav.style.marginTop = '10px';
        topNav.style.flexWrap = 'wrap';
    }

    // 插入底部导航
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
