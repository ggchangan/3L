const CAT_NAMES = ['公司', '行业', '研报', '逻辑'];
        const CAT_ICONS = { '公司': '🏢', '行业': '📊', '研报': '📄', '逻辑': '🧠' };
        const CAT_COLORS = { '公司': '#22c55e', '行业': '#3b82f6', '研报': '#a855f7', '逻辑': '#f59e0b' };

        (async function() {
            try {
                const res = await fetch('/api/industry/list');
                const data = await res.json();
                document.getElementById('loading-area').style.display = 'none';
                document.getElementById('main-content').style.display = 'block';

                // Group by category
                const grouped = {};
                CAT_NAMES.forEach(c => grouped[c] = []);

                (data.items || []).forEach(item => {
                    const cat = item.category || '公司';
                    if (!grouped[cat]) grouped[cat] = [];
                    grouped[cat].push(item);
                });

                // Build tabs
                const tabsEl = document.getElementById('cat-tabs');
                let firstNonEmpty = null;
                tabsEl.innerHTML = CAT_NAMES.map((cat, idx) => {
                    const count = (grouped[cat] || []).length;
                    if (count > 0 && !firstNonEmpty) firstNonEmpty = cat;
                    return `<div class="cat-tab ${idx === 0 ? 'active' : ''}" onclick="switchCat('${cat}')" data-cat="${cat}">
                        ${CAT_ICONS[cat] || ''} ${cat} <span class="count">${count}</span>
                    </div>`;
                }).join('');

                // Build sections
                CAT_NAMES.forEach(cat => {
                    const items = grouped[cat] || [];
                    const el = document.getElementById(`cat-${cat}`);
                    if (items.length === 0) {
                        el.innerHTML = `<div class="empty-cat">暂无${cat}分析</div>`;
                        return;
                    }
                    el.className = 'cat-section' + (cat === firstNonEmpty ? ' active' : '');
                    el.innerHTML = `<div class="kb-grid">${items.map(item => {
                        const tagCls = cat === '公司' ? 'company-tag' : cat === '行业' ? 'industry-tag' : cat === '研报' ? 'report-tag' : 'logic-tag';
                        return `<div class="kb-card">
                            <span class="tag ${tagCls}">${CAT_ICONS[cat] || ''} ${cat}</span>
                            <h3>${item.title}</h3>
                            ${item.date_added ? `<div class="date">📅 收录 ${item.date_added}</div>` : ''}
                            <p>${item.desc || '暂无摘要'}</p>
                            <div>
                                <a class="btn btn-read" href="/tip-detail.html?type=industry&file=${encodeURIComponent(item.file)}">📖 阅读全文</a>
                            </div>
                        </div>`;
                    }).join('')}</div>`;
                });

                // Auto-switch to first non-empty tab
                if (firstNonEmpty) switchCat(firstNonEmpty);

            } catch(e) {
                document.getElementById('loading-area').innerHTML = `<div style="color:#e94560;">❌ 加载失败: ${e.message}</div>`;
            }
        })();

        function switchCat(cat) {
            document.querySelectorAll('.cat-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.cat-section').forEach(s => s.classList.remove('active'));
            document.querySelector(`.cat-tab[data-cat="${cat}"]`).classList.add('active');
            document.getElementById(`cat-${cat}`).classList.add('active');
        }