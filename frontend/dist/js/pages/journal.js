// --- Stock Search ---
        let allStocks = [];
        async function loadStocks() {
            try {
                const res = await fetch('/api/tips');
                // 也可以直接通过stock-analysis搜索
            } catch(e) {}
            // 尝试从数据层加载全部股票
            try {
                const res = await fetch('/api/tips/journal-entries'); 
            } catch(e) {}
            // 使用预置的常用自选股列表作为搜索源
            allStocks = [];
        }

        const stockInput = document.getElementById('j-stock');
        const stockDropdown = document.getElementById('stock-dropdown');
        let searchTimer = null;

        stockInput.addEventListener('input', function() {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => searchStock(this.value), 200);
        });
        stockInput.addEventListener('focus', function() {
            if (this.value) searchStock(this.value);
        });
        document.addEventListener('click', function(e) {
            if (!e.target.closest('.stock-search-wrap')) stockDropdown.classList.remove('show');
        });

        async function searchStock(q) {
            if (!q || q.length < 1) { stockDropdown.classList.remove('show'); return; }
            try {
                const res = await fetch(`/api/stock-analysis?q=${encodeURIComponent(q)}`);
                const data = await res.json();
                stockDropdown.innerHTML = '';
                if (data.code) {
                    const opt = document.createElement('div');
                    opt.className = 'opt';
                    opt.textContent = `${data.name} (${data.code}) — ${data.direction || ''}`;
                    opt.onclick = () => selectStock(data.name, data.code);
                    stockDropdown.appendChild(opt);
                    stockDropdown.classList.add('show');
                } else {
                    stockDropdown.innerHTML = '<div class="opt" style="color:#666;">未找到</div>';
                    stockDropdown.classList.add('show');
                }
            } catch(e) {
                stockDropdown.classList.remove('show');
            }
        }

        function selectStock(name, code) {
            stockInput.value = `${name} (${code})`;
            stockDropdown.classList.remove('show');
        }

        // --- Tabs ---
        function switchTab(tab) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelector(`.tab[onclick*="${tab}"]`).classList.add('active');
            document.getElementById(`tab-${tab}`).classList.add('active');
            if (tab === 'history') loadHistory();
        }

        // --- Save ---
        async function saveJournal() {
            const data = {
                date: document.getElementById('j-date').value || new Date().toISOString().slice(0,10),
                stock: stockInput.value,
                reason: document.getElementById('j-reason').value,
                stop_loss: document.getElementById('j-stop-loss').value,
                point: document.getElementById('j-point').value,
                pnl: document.getElementById('j-pnl').value,
                score: document.getElementById('j-score').value,
                emotion: document.getElementById('j-emotion').value,
                reflection: document.getElementById('j-reflection').value,
            };

            if (!data.stock) { showToast('请输入标的', 'error'); return; }
            if (!data.reason) { showToast('请输入买入理由/逻辑', 'error'); return; }

            try {
                const res = await fetch('/api/tips/save-journal', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(data)
                });
                const result = await res.json();
                if (result.status === 'ok') {
                    showToast('✅ 日志保存成功！', 'success');
                    clearForm();
                } else {
                    showToast('❌ ' + (result.msg || '保存失败'), 'error');
                }
            } catch(e) {
                showToast('❌ ' + e.message, 'error');
            }
        }

        function clearForm() {
            document.getElementById('j-stock').value = '';
            document.getElementById('j-reason').value = '';
            document.getElementById('j-stop-loss').value = '';
            document.getElementById('j-point').value = '';
            document.getElementById('j-pnl').value = '';
            document.getElementById('j-score').value = '';
            document.getElementById('j-emotion').value = '';
            document.getElementById('j-reflection').value = '';
        }

        // --- Toast ---
        function showToast(msg, type) {
            const t = document.getElementById('toast');
            t.textContent = msg;
            t.className = `toast ${type}`;
            t.style.display = 'block';
            setTimeout(() => { t.style.display = 'none'; }, 3000);
        }

        // --- History ---
        async function loadHistory() {
            const el = document.getElementById('history-list');
            el.className = 'loading';
            el.innerHTML = '<div class="spinner"></div><br>加载中...';
            try {
                const res = await fetch('/api/tips/journal-entries');
                const data = await res.json();
                const entries = data.entries || [];
                if (entries.length === 0) {
                    el.innerHTML = '<div class="empty">暂无交易日志记录<br><span style="font-size:12px;color:#555;">切换到「写日志」开始记录吧</span></div>';
                    return;
                }
                el.className = 'history-list';
                el.innerHTML = entries.map((e, i) => `
                    <div class="history-item" onclick="showDetail(${i})">
                        <div class="h-top">
                            <span class="h-date">${e.date}</span>
                            <span class="h-stock">${e.stock || '--'}</span>
                            <span class="h-score" style="color:${getScoreColor(e.score)}">${e.score ? e.score + '/10' : '--'}</span>
                        </div>
                        <div class="h-reason">
                            ${(e.reason || '').slice(0, 80)}${(e.reason || '').length > 80 ? '...' : ''}
                            ${e.pnl ? ' · <span style="color:' + (parseFloat(e.pnl) >= 0 ? '#22c55e' : '#e94560') + '">' + e.pnl + '%</span>' : ''}
                        </div>
                    </div>
                `).join('');
                // Store data for detail view
                window._journalEntries = entries;
            } catch(e) {
                el.innerHTML = `<div class="empty">❌ 加载失败: ${e.message}</div>`;
            }
        }

        function getScoreColor(s) {
            const n = parseInt(s);
            if (n >= 8) return '#22c55e';
            if (n >= 6) return '#f59e0b';
            return '#e94560';
        }

        function showDetail(idx) {
            const entries = window._journalEntries || [];
            const e = entries[idx];
            if (!e) return;
            document.getElementById('detail-title').textContent = `${e.date} · ${e.stock || '--'}`;
            document.getElementById('detail-body').innerHTML = `
                <div class="field"><div class="fl">③ 理由/逻辑</div><div class="fv">${e.reason || '--'}</div></div>
                <div class="field"><div class="fl">④ 止损点</div><div class="fv">${e.stop_loss || '--'}</div></div>
                <div class="field"><div class="fl">⑤ 买卖点</div><div class="fv">${e.point || '--'}</div></div>
                <div class="field"><div class="fl">⑥ 盈亏</div><div class="fv" style="color:${parseFloat(e.pnl) >= 0 ? '#22c55e' : '#e94560'}">${e.pnl || '--'}%</div></div>
                <div class="field"><div class="fl">⑧ 执行评分</div><div class="fv" style="color:${getScoreColor(e.score)}">${e.score || '--'}/10</div></div>
                <div class="field"><div class="fl">⑨ 情绪</div><div class="fv">${e.emotion || '--'}</div></div>
                <div class="field"><div class="fl">⑩ 反思</div><div class="fv">${e.reflection || '--'}</div></div>
                <div class="field"><div class="fl">创建时间</div><div class="fv" style="color:#888;font-size:12px;">${e.created_at || '--'}</div></div>
            `;
            document.getElementById('detail-overlay').classList.add('show');
        }

        function closeDetail() {
            document.getElementById('detail-overlay').classList.remove('show');
        }

        // Set default date
        document.getElementById('j-date').value = new Date().toISOString().slice(0,10);

        // Load history if first tab
        loadHistory();