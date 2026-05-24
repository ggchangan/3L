(async function() {
            const el = document.getElementById('tips-list');
            try {
                const res = await fetch('/api/tips');
                const data = await res.json();
                if (!data.tips || data.tips.length === 0) {
                    el.innerHTML = '<div class="empty">暂无交易技巧</div>';
                    return;
                }
                el.className = 'tips-grid';
                el.innerHTML = data.tips.map(t => {
                    const readLink = `/tip-detail.html?type=tips&file=${encodeURIComponent(t.file)}`;
                    if (t.is_journal) {
                        return `<div class="tip-card">
                            <div>
                                <span class="badge">📖 技巧</span>
                                <span class="badge badge-tool">✍️ 互动工具</span>
                            </div>
                            <h3>${t.title}</h3>
                            ${t.date_added ? `<div class="date">📅 收录 ${t.date_added}</div>` : ''}
                            <p>${t.desc || '暂无摘要'}</p>
                            <div class="tip-actions">
                                <a class="btn btn-read" href="${readLink}">📖 阅读文章</a>
                                <a class="btn btn-tool" href="/journal.html">✍️ 写日志</a>
                            </div>
                        </div>`;
                    }
                    return `<div class="tip-card">
                        <h3>${t.title}</h3>
                        ${t.date_added ? `<div class="date">📅 收录 ${t.date_added}</div>` : ''}
                        <p>${t.desc || '暂无摘要'}</p>
                        <div class="tip-actions">
                            <a class="btn btn-read" href="${readLink}">📖 阅读全文</a>
                        </div>
                    </div>`;
                }).join('');
            } catch(e) {
                el.innerHTML = `<div class="empty">❌ 加载失败: ${e.message}</div>`;
            }
        })();