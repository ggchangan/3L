// Set today's date
        const d = new Date();
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
        const wd = weekdays[d.getDay()];
        const todayStr = `${y}-${m}-${day}`;
        document.getElementById('todayDate').textContent = `${todayStr} 星期${wd}`;
        document.getElementById('todayMeta').textContent = `${todayStr} 生成`;

        // File descriptions mapping
        const fileDesc = {
            'A股数据源验证报告_20260519.pdf': 'A股数据源验证报告 · 5数据源全测',
            '每日成果_20260519.pdf': '3L每日成果记录 · 持仓修复+下载修复+模拟引擎',
            '每日成果_20260520.pdf': '3L每日成果记录 · 盘中盯盘+市场龙头扫描+3L待办体系',
            '3层缩量阈值框架_20260521.pdf': '3层缩量/放量阈值动态调整框架 · 大盘+板块+个股递进模型',
            '每日成果_20260521.pdf': '3L每日成果记录 · 复盘修复+资金流向图+EMA算法修正',
            '操作建议调优过程_20260521.pdf': '操作建议调优过程记录 · 2026-05-21',
            '每日复盘上线_20260520.pdf': '📋 每日复盘页面 · 首版上线报告（大盘/行业/个股/信号全模块）',
            '趋势股的交易方法_20260522.pdf': '趋势股交易方法 v3.0 — 双系统+乖离率定位+跟踪止盈+全量回测数据',
        '算法讨论纪要_20260522.pdf': '3L算法改进讨论纪实：趋势股判定、加速误判、D方案设计过程，含12只加速股验证',
        '加速判定算法_20260522.pdf': '加速判定算法D方案完整纪要—乖离率两步法确认过程+12验证案例+流程图',
        '结构判定算法最终方案_20260522.pdf': '结构判定算法最终方案—EMA10对称校验+流程图+14只下降趋势名单',
        '波峰波谷判定_V5方案.pdf': 'V5算法全文档：背景、探索过程(V1~V5)、算法详情、量价信号、3指数回测结果、与旧方案对比',
        '买点信号回测报告_20260522.pdf': '买点信号历史回测报告—328只自选股60天历史，统计中继/突破买点的胜率、平均R倍数、盈亏比',
        '德明利_3L优化回测报告.pdf': '德明利(001309) 90天回测—13个买点信号验证六大规则优化效果',
        '德明利_R4量比1.1报告_20260524.pdf': '德明利R4回测—量比>1.1/7笔交易/K线图/每笔明细/累计收益+61.40%',
        };

        // Load files from /pub/files/ directory listing
        fetch('/pub/files/?v=' + Date.now())
            .then(r => r.json())
            .then(data => {
                const pdfs = [];
                const otherFiles = [];
                for (const href of (data.files || [])) {
                    const name = decodeURIComponent(href);
                    if (name.endsWith('.pdf')) {
                        pdfs.push({ name, url: '/pub/files/' + href });
                    } else {
                        otherFiles.push({ name, url: '/pub/files/' + href });
                    }
                }
                // Sort: newest first (by name which has date prefix)
                pdfs.sort().reverse();

                // Update stats (optional - no longer displayed but kept for data)
                const totalPdfs = pdfs.length;

                // Populate today's files (only today's PDFs)
                const todayFiles = document.getElementById('todayFiles');
                todayFiles.innerHTML = '';
                const todayCompact = todayStr.replace(/-/g, '');
                const todayPDFs = pdfs.filter(p => p.name.includes(todayCompact));
                
                todayPDFs.forEach((pdf, idx) => {
                    const desc = fileDesc[pdf.name] || pdf.name.replace('.pdf', '').replace(/_/g, ' ');
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <span class="file-name">${desc} <span class="tag pdf">PDF</span>${idx === 0 ? ' <span class="tag new">NEW</span>' : ''}</span>
                        <a href="${pdf.url}" target="_blank" style="color:#e94560; text-decoration:none; font-size:13px;">下载</a>
                    `;
                    todayFiles.appendChild(li);
                });

                // Populate history (daily achievement reports grouped by date, excluding today)
                const historyList = document.getElementById('historyList');
                historyList.innerHTML = '';
                
                const dailyReports = pdfs.filter(p => p.name.match(/^\u6bcf\u65e5\u6210\u679c_\d{8}\.pdf$/));
                const dateGroups = {};
                dailyReports.forEach(pdf => {
                    const match = pdf.name.match(/^\u6bcf\u65e5\u6210\u679c_(\d{8})\.pdf$/);
                    if (match) {
                        const d = `${match[1].slice(0,4)}-${match[1].slice(4,6)}-${match[1].slice(6,8)}`;
                        if (d !== todayStr) {
                            if (!dateGroups[d]) dateGroups[d] = [];
                            dateGroups[d].push(pdf);
                        }
                    }
                });

                Object.keys(dateGroups).sort().reverse().forEach(date => {
                    const pdf = dateGroups[date][0];
                    const desc = fileDesc[pdf.name] || '3L每日成果';
                    const li = document.createElement('li');
                    li.innerHTML = `
                        <div>
                            <span class="h-date">${date}</span>
                            <span class="h-title">${desc}</span>
                        </div>
                        <div class="h-link">
                            <a href="/archive/${date}.html" target="_blank" style="color:#4ecdc4; text-decoration:none; font-size:13px;">查看</a>
                            <a href="${pdf.url}" target="_blank" style="color:#e94560; text-decoration:none; font-size:13px; margin-left:10px;">📄</a>
                        </div>
                    `;
                    historyList.appendChild(li);
                });
            })
            .catch(() => {
                // Fallback - keep empty
            });