// 各周交易数据和PKL文件名
        const WEEKS = ['w1', 'w2', 'w3', 'w4'];
        const WEEK_LABELS = { w1: '第1周 (4/7~4/10)', w2: '第2周 (4/13~4/17)', w3: '第3周 (4/20~4/24)', w4: '第4周 (4/27~4/30)' };
        const WEEK_PNLS = { w1: '+7.68%', w2: '-0.88%', w3: '-2.10%', w4: '+3.34%' };
        const WEEK_TRADES = { w1: 13, w2: 27, w3: 28, w4: 16 };
        const WEEK_MAIN = { w1: '半导体', w2: '创新药→算力', w3: '商业航天→算力', w4: '半导体' };
        const WEEK_REPORT = { w1: '/pub/files/模拟交易v33_第1周报告.pdf', w2: '/pub/files/模拟交易v33_第2周报告.pdf', w3: '/pub/files/模拟交易v33_第3周报告.pdf', w4: '/pub/files/模拟交易v33_第4周报告.pdf' };

        // 交易数据（从PKL中提取的缩略版）
        const TRADE_DATA = {
            w1: [
                {date:"0408", dir:"买入", code:"688693", name:"锴威特", sector:"半导体", type:"突破买点", qty:2900, price:66.92},
                {date:"0408", dir:"买入", code:"300236", name:"上海新阳", sector:"半导体", type:"突破买点", qty:2400, price:81.01},
                {date:"0408", dir:"买入", code:"002008", name:"大族激光", sector:"半导体", type:"突破买点", qty:2800, price:70.8},
                {date:"0408", dir:"买入", code:"300604", name:"长川科技", sector:"半导体", type:"突破买点", qty:1500, price:130.51},
                {date:"0408", dir:"买入", code:"600584", name:"长电科技", sector:"半导体", type:"突破买点", qty:2500, price:41.98},
                {date:"0408", dir:"买入", code:"688347", name:"华虹公司", sector:"半导体", type:"突破买点", qty:400, price:120.28},
                {date:"0408", dir:"买入", code:"300346", name:"南大光电", sector:"半导体", type:"突破买点", qty:600, price:48.18},
                {date:"0408", dir:"买入", code:"300058", name:"蓝色光标", sector:"AI应用", type:"突破买点", qty:1000, price:16.31},
                {date:"0408", dir:"买入", code:"603890", name:"春秋电子", sector:"算力", type:"突破买点", qty:600, price:15.61},
                {date:"0408", dir:"买入", code:"688010", name:"福光股份", sector:"商业航天", type:"突破买点", qty:100, price:33.06},
                {date:"0408", dir:"买入", code:"300580", name:"贝斯特", sector:"机器人", type:"突破买点", qty:100, price:24.83},
                {date:"0408", dir:"买入", code:"688590", name:"新致软件", sector:"AI应用", type:"突破买点", qty:100, price:14.4},
                {date:"0409", dir:"卖半", code:"688590", name:"新致软件", sector:"AI应用", type:"左侧止盈减半", qty:50, price:14.43},
            ],
            w2: [
                {date:"0413", dir:"买入", code:"002653", name:"海思科", sector:"创新药", type:"突破买点", qty:3200, price:60.63},
                {date:"0413", dir:"买入", code:"688008", name:"澜起科技", sector:"半导体", type:"突破买点", qty:600, price:152.3},
                {date:"0413", dir:"买入", code:"300042", name:"朗科科技", sector:"半导体", type:"突破买点", qty:2000, price:49.7},
                {date:"0413", dir:"买入", code:"301308", name:"江波龙", sector:"半导体", type:"突破买点", qty:200, price:354.5},
                {date:"0413", dir:"买入", code:"600176", name:"中国巨石", sector:"算力", type:"突破买点", qty:3100, price:32.11},
                {date:"0413", dir:"买入", code:"002364", name:"中恒电气", sector:"算力", type:"突破买点", qty:2500, price:38.63},
                {date:"0413", dir:"买入", code:"000988", name:"华工科技", sector:"算力", type:"突破买点", qty:700, price:125.16},
                {date:"0414", dir:"卖半", code:"002364", name:"中恒电气", sector:"算力", type:"左侧止盈减半", qty:1250, price:42.49},
                {date:"0414", dir:"买入", code:"603005", name:"晶方科技", sector:"半导体", type:"突破买点", qty:5100, price:30.3},
                {date:"0414", dir:"买入", code:"688766", name:"普冉股份", sector:"半导体", type:"突破买点", qty:200, price:271.03},
                {date:"0414", dir:"买入", code:"301509", name:"金凯生科", sector:"创新药", type:"突破买点", qty:1100, price:47.16},
                {date:"0414", dir:"买入", code:"300347", name:"泰格医药", sector:"创新药", type:"突破买点", qty:400, price:59.45},
                {date:"0414", dir:"买入", code:"002463", name:"沪电股份", sector:"算力", type:"突破买点", qty:100, price:97.54},
                {date:"0415", dir:"卖出", code:"688008", name:"澜起科技", sector:"半导体", type:"右侧止盈", qty:600, price:147.18},
                {date:"0415", dir:"卖出", code:"300042", name:"朗科科技", sector:"半导体", type:"右侧止盈", qty:2000, price:48.77},
                {date:"0415", dir:"卖出", code:"000988", name:"华工科技", sector:"算力", type:"止损", qty:700, price:112.3},
                {date:"0415", dir:"卖出", code:"002463", name:"沪电股份", sector:"算力", type:"右侧止盈", qty:100, price:92.78},
                {date:"0415", dir:"买入", code:"603115", name:"海星股份", sector:"元件", type:"中继买点", qty:2200, price:44.5},
                {date:"0415", dir:"买入", code:"688428", name:"诺诚健华", sector:"创新药", type:"突破买点", qty:3100, price:31.17},
                {date:"0415", dir:"买入", code:"301248", name:"杰创智能", sector:"AI应用", type:"突破买点", qty:800, price:57.75},
                {date:"0415", dir:"买入", code:"601179", name:"中国西电", sector:"算力", type:"突破买点", qty:1400, price:17.7},
                {date:"0416", dir:"卖出", code:"002653", name:"海思科", sector:"创新药", type:"止损", qty:3200, price:56.85},
                {date:"0416", dir:"买入", code:"688548", name:"广钢气体", sector:"半导体", type:"突破买点", qty:3800, price:26.01},
                {date:"0417", dir:"卖出", code:"002364", name:"中恒电气", sector:"算力", type:"右侧止盈", qty:1250, price:40.91},
                {date:"0417", dir:"卖出", code:"301509", name:"金凯生科", sector:"创新药", type:"右侧止盈", qty:1100, price:44.53},
                {date:"0417", dir:"买入", code:"300502", name:"新易盛", sector:"算力", type:"突破买点", qty:100, price:589.0},
                {date:"0417", dir:"买入", code:"001389", name:"广合科技", sector:"算力", type:"突破买点", qty:500, price:149.22},
            ],
            w3: [
                {date:"0420", dir:"买入", code:"600118", name:"中国卫星", sector:"商业航天", type:"突破买点", qty:2100, price:94.52},
                {date:"0420", dir:"买入", code:"002149", name:"西部材料", sector:"商业航天", type:"突破买点", qty:3300, price:60.28},
                {date:"0420", dir:"买入", code:"600879", name:"航天电子", sector:"商业航天", type:"突破买点", qty:7800, price:25.53},
                {date:"0420", dir:"买入", code:"002475", name:"立讯精密", sector:"算力", type:"突破买点", qty:3000, price:65.73},
                {date:"0420", dir:"买入", code:"600330", name:"天通股份", sector:"算力", type:"突破买点", qty:4300, price:23.9},
                {date:"0420", dir:"买入", code:"002837", name:"英维克", sector:"算力", type:"突破买点", qty:400, price:121.08},
                {date:"0420", dir:"买入", code:"300699", name:"光威复材", sector:"商业航天", type:"突破买点", qty:700, price:37.04},
                {date:"0421", dir:"卖半", code:"600330", name:"天通股份", sector:"算力", type:"左侧止盈减半", qty:2150, price:23.52},
                {date:"0421", dir:"卖出", code:"002837", name:"英维克", sector:"算力", type:"止损", qty:400, price:108.97},
                {date:"0421", dir:"买入", code:"002342", name:"巨力索具", sector:"商业航天", type:"突破买点", qty:2800, price:21.42},
                {date:"0421", dir:"买入", code:"603017", name:"中衡设计", sector:"算力", type:"突破买点", qty:2000, price:15.63},
                {date:"0421", dir:"买入", code:"002436", name:"兴森科技", sector:"算力", type:"突破买点", qty:500, price:28.21},
                {date:"0421", dir:"买入", code:"601728", name:"中国电信", sector:"算力", type:"突破买点", qty:1400, price:6.0},
                {date:"0421", dir:"买入", code:"601991", name:"大唐发电", sector:"新能源", type:"突破买点", qty:1100, price:4.11},
                {date:"0421", dir:"买入", code:"000559", name:"万向钱潮", sector:"机器人", type:"突破买点", qty:100, price:17.27},
                {date:"0423", dir:"卖半", code:"600118", name:"中国卫星", sector:"商业航天", type:"左侧止盈减半", qty:1050, price:102.0},
                {date:"0423", dir:"卖出", code:"600330", name:"天通股份", sector:"算力", type:"右侧止盈", qty:2150, price:25.6},
                {date:"0423", dir:"卖出", code:"300699", name:"光威复材", sector:"商业航天", type:"右侧止盈", qty:700, price:35.79},
                {date:"0423", dir:"卖出", code:"002342", name:"巨力索具", sector:"商业航天", type:"止损", qty:2800, price:18.96},
                {date:"0423", dir:"买入", code:"001267", name:"汇绿生态", sector:"算力", type:"突破买点", qty:1900, price:50.92},
                {date:"0423", dir:"买入", code:"002008", name:"大族激光", sector:"半导体", type:"突破买点", qty:700, price:103.6},
                {date:"0423", dir:"买入", code:"600726", name:"华电能源", sector:"资源股", type:"突破买点", qty:7000, price:5.27},
                {date:"0424", dir:"卖出", code:"600118", name:"中国卫星", sector:"商业航天", type:"右侧止盈", qty:1050, price:96.3},
                {date:"0424", dir:"卖出", code:"002149", name:"西部材料", sector:"商业航天", type:"右侧止盈", qty:3300, price:57.9},
                {date:"0424", dir:"卖出", code:"600879", name:"航天电子", sector:"商业航天", type:"右侧止盈", qty:7800, price:23.62},
                {date:"0424", dir:"买入", code:"688347", name:"华虹公司", sector:"半导体", type:"突破买点", qty:1400, price:138.8},
                {date:"0424", dir:"买入", code:"688141", name:"杰华特", sector:"半导体", type:"突破买点", qty:1900, price:83.1},
                {date:"0424", dir:"买入", code:"688041", name:"海光信息", sector:"半导体", type:"突破买点", qty:200, price:285.0},
            ],
            w4: [
                {date:"0427", dir:"买入", code:"688012", name:"中微公司", sector:"半导体", type:"突破买点", qty:500, price:352.01},
                {date:"0427", dir:"买入", code:"688409", name:"富创精密", sector:"半导体", type:"突破买点", qty:1600, price:120.42},
                {date:"0427", dir:"买入", code:"300604", name:"长川科技", sector:"半导体", type:"突破买点", qty:1100, price:175.02},
                {date:"0427", dir:"买入", code:"688183", name:"生益电子", sector:"算力", type:"突破买点", qty:1600, price:120.7},
                {date:"0427", dir:"买入", code:"688127", name:"蓝特光学", sector:"半导体", type:"中继买点", qty:1400, price:69.31},
                {date:"0427", dir:"买入", code:"300788", name:"中信出版", sector:"半导体", type:"中继买点", qty:2000, price:36.7},
                {date:"0427", dir:"买入", code:"603986", name:"兆易创新", sector:"半导体", type:"中继买点", qty:100, price:303.42},
                {date:"0428", dir:"买入", code:"000066", name:"中国长城", sector:"算力", type:"突破买点", qty:1200, price:17.83},
                {date:"0428", dir:"买入", code:"688246", name:"嘉和美康", sector:"AI应用", type:"突破买点", qty:500, price:21.3},
                {date:"0428", dir:"买入", code:"601177", name:"杭齿前进", sector:"机器人", type:"突破买点", qty:300, price:16.25},
                {date:"0428", dir:"买入", code:"600152", name:"维科技术", sector:"新能源", type:"突破买点", qty:200, price:15.69},
                {date:"0428", dir:"买入", code:"688126", name:"沪硅产业", sector:"半导体", type:"中继买点", qty:100, price:20.58},
                {date:"0429", dir:"卖出", code:"688183", name:"生益电子", sector:"算力", type:"止损", qty:1600, price:114.17},
                {date:"0429", dir:"卖出", code:"600152", name:"维科技术", sector:"新能源", type:"止损", qty:200, price:14.5},
                {date:"0429", dir:"买入", code:"688390", name:"固德威", sector:"新能源", type:"突破买点", qty:900, price:101.63},
                {date:"0429", dir:"买入", code:"300438", name:"鹏辉能源", sector:"新能源", type:"突破买点", qty:500, price:81.0},
            ],
        };
        const container = document.getElementById('weeksContainer');

        WEEKS.forEach(wk => {
            const div = document.createElement('div');
            div.className = 'week-card';

            const pnl = WEEK_PNLS[wk];
            const pnlClass = pnl.startsWith('+') ? 'w-pnl' : 'w-pnl neg';

            let html = `<div class="w-title">${WEEK_LABELS[wk]} <span class="${pnlClass}">${pnl}</span> <span style="color:#888;font-size:12px;font-weight:normal;margin-left:8px;">方向: ${WEEK_MAIN[wk]} | ${WEEK_TRADES[wk]}笔</span> <a href="${WEEK_REPORT[wk]}" target="_blank" style="color:#4ecdc4;text-decoration:none;font-size:11px;margin-left:8px;">📄 周报告</a></div>`;

            const trades = TRADE_DATA[wk];
            if (trades && trades.length > 0) {
                html += '<table><thead><tr><th>日期</th><th>方向</th><th>代码</th><th>名称</th><th>方向</th><th>买点类型</th><th>数量</th><th>价格</th></tr></thead><tbody>';
                trades.forEach(t => {
                    const dirClass = t.dir === '买入' ? 'buy' : t.dir === '卖出' ? 'sell' : '';
                    html += `<tr>
                        <td>${t.date}</td>
                        <td class="${dirClass}">${t.dir}</td>
                        <td>${t.code}</td>
                        <td>${t.name}</td>
                        <td>${t.sector}</td>
                        <td>${t.type}</td>
                        <td>${t.qty}</td>
                        <td>${t.price}</td>
                    </tr>`;
                });
                html += '</tbody></table>';
            }

            div.innerHTML = html;
            container.appendChild(div);
        });