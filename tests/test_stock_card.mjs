/**
 * stock_card.js 单元测试 + 回归测试
 * signalStockCard() 是纯函数（输入数据对象→HTML字符串）
 * 使用 Node.js 内置 assert，零外部依赖
 */
import { strict as assert } from 'node:assert';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { signalStockCard } = require('../js/stock_card.js');

/* ========== 测试辅助 ========== */
let pass = 0, fail = 0;
function test(name, fn) {
    try {
        fn();
        pass++;
        console.log(`  ✅ ${name}`);
    } catch (e) {
        fail++;
        console.log(`  ❌ ${name}`);
        console.log(`     期望: ${JSON.stringify(e.expected)}`);
        console.log(`     实际: ${JSON.stringify(e.actual)}`);
        console.log(`     位置: ${e.stack?.split('\n').slice(1, 3).join(' → ')}`);
    }
}

function contains(html, ...patterns) {
    for (const p of patterns) {
        if (!html.includes(p)) {
            throw { expected: `包含 "${p}"`, actual: html.slice(0, 200) };
        }
    }
}

function notContains(html, ...patterns) {
    for (const p of patterns) {
        if (html.includes(p)) {
            throw { expected: `不包含 "${p}"`, actual: html.slice(0, 200) };
        }
    }
}

// 模拟 toggleChart 全局函数
globalThis.toggleChart = () => {};

/* ========== 模拟数据 ========== */
const baseStock = {
    name: '贵州茅台',
    code: '600519',
    price: 1580.50,
    change: 2.35,
    sector: '白酒',
    structure: '上涨趋势',
    stage: '上行',
    signal: 'hold',
    trading_system: '3l',
    vol_analysis: '缩量',
    buy_point: '突破买点',
    profit_model1: false,
    trend_stock: false,
};

/* ===================================================== */
/* 第1轮：基础渲染测试                                      */
/* ===================================================== */
console.log('\n📦 第1轮：基础渲染');
{
    const html = signalStockCard(baseStock, 0);
    test('渲染非空字符串', () => assert(html.length > 100));
    test('包含股票名称', () => contains(html, '贵州茅台'));
    test('包含股票代码', () => contains(html, '600519'));
    test('包含价格', () => contains(html, '1580.50'));
    test('包含涨幅（正数带+号）', () => contains(html, '+2.35%'));
    test('包含板块', () => contains(html, '白酒'));
    test('包含结构', () => contains(html, '上涨趋势'));
    test('包含阶段', () => contains(html, '上行'));
    test('包含图表容器', () => contains(html, 'hchart_0'));
    test('图表ID不重复', () => {
        const id0 = signalStockCard(baseStock, 0);
        const id1 = signalStockCard(baseStock, 1);
        contains(id0, 'hchart_0');
        contains(id1, 'hchart_1');
    });
    test('chart-container 初始隐藏', () => contains(html, 'display:none'));
    test('包含object标签加载SVG', () => contains(html, 'object', 'svg'));
    test('SVG路径含code', () => contains(html, '600519.svg'));
    test('包含toggleChart onclick', () => contains(html, "toggleChart('hchart_0')"));
}

/* ===================================================== */
/* 第2轮：交易系统测试                                     */
/* ===================================================== */
console.log('\n🔥 第2轮：交易系统');
{
    const trend = signalStockCard({ ...baseStock, trading_system: 'trend', trading_reason: '结构上涨+斜率>3%+主线方向' }, 0);
    test('趋势交易 → 🔥趋势交易', () => contains(trend, '🔥趋势交易'));
    test('趋势交易含判定原因（title）', () => contains(trend, '结构上涨+斜率>3%+主线方向'));

    const l3 = signalStockCard({ ...baseStock, trading_system: '3l' }, 0);
    test('3L交易 → 📘3L交易', () => contains(l3, '📘3L交易'));

    const ns = signalStockCard({ ...baseStock, trading_system: undefined }, 0);
    test('无system → 默认3L', () => contains(ns, '📘3L交易'));
}

/* ===================================================== */
/* 第3轮：操作信号测试                                     */
/* ===================================================== */
console.log('\n⚡ 第3轮：操作信号');
{
    test('hold → ✅持有', () => {
        const h = signalStockCard({ ...baseStock, signal: 'hold' }, 0);
        contains(h, '✅持有');
        contains(h, 'border-left:3px solid'); // hold色
    });
    test('buy → ⚡买入', () => {
        const b = signalStockCard({ ...baseStock, signal: 'buy' }, 0);
        contains(b, '⚡买入');
        contains(b, 'warn');
    });
    test('sell → ❌卖出', () => {
        const s = signalStockCard({ ...baseStock, signal: 'sell' }, 0);
        contains(s, '❌卖出');
        contains(s, 'danger');
    });
    test('无signal → --', () => {
        const n = signalStockCard({ ...baseStock, signal: undefined }, 0);
        contains(n, '--');
    });
}

/* ===================================================== */
/* 第4轮：阶段图标和颜色                                    */
/* ===================================================== */
console.log('\n🎨 第4轮：阶段映射');
{
    const stages = {
        '上行': '↑', '加速': '🚀', '缩量整理': '🔄', '滞涨': '⚠️',
        '转弱': '📉', '下行': '↓', '加速跌': '📉', '转强': '📈',
        '区间底部': '🟢', '区间中段': '➡️', '区间顶部': '🔴',
    };
    for (const [stage, icon] of Object.entries(stages)) {
        test(`阶段"${stage}" → icon"${icon}"`, () => {
            const h = signalStockCard({ ...baseStock, stage }, 0);
            contains(h, icon);
        });
    }
    test('未知阶段 → fallback圆点', () => {
        const h = signalStockCard({ ...baseStock, stage: '未知阶段' }, 0);
        contains(h, '•');
    });
    // 检查颜色非空
    test('每个阶段都有配色', () => {
        for (const stage of Object.keys(stages)) {
            const h = signalStockCard({ ...baseStock, stage }, 0);
            assert(h.includes('border-left:3px solid'), `阶段${stage}缺左边框颜色`);
        }
    });
}

/* ===================================================== */
/* 第5轮：结构图标测试                                     */
/* ===================================================== */
console.log('\n📊 第5轮：结构映射');
{
    test('上涨趋势 → 📈', () => contains(signalStockCard({ ...baseStock, structure: '上涨趋势' }, 0), '📈'));
    test('区间震荡 → ➡️', () => contains(signalStockCard({ ...baseStock, structure: '区间震荡' }, 0), '➡️'));
    test('下降趋势 → 📉', () => contains(signalStockCard({ ...baseStock, structure: '下降趋势' }, 0), '📉'));
    test('其他结构 → 无图标', () => {
        const h = signalStockCard({ ...baseStock, structure: '其他' }, 0);
        assert(!h.includes('📈') && !h.includes('➡️') && !h.includes('📉'));
    });
}

/* ===================================================== */
/* 第6轮：买点显示测试                                     */
/* ===================================================== */
console.log('\n🎯 第6轮：买点');
{
    // 趋势股 + 乖离率买点
    const trendBuy = signalStockCard({
        ...baseStock, trading_system: 'trend',
        trend_buy_type: 'BIAS5乖离率买入', trend_bias: 1.11
    }, 0);
    test('趋势买点：买入区颜色', () => contains(trendBuy, '#4ecdc4'));
    test('趋势买点：含BIAS值', () => contains(trendBuy, 'BIAS=1.11%'));
    test('趋势买点：含买入区标签', () => contains(trendBuy, '乖离率买入区'));

    // 趋势股 + 乖离率买入区（负值）
    const negBias = signalStockCard({
        ...baseStock, trading_system: 'trend',
        trend_buy_type: 'BIAS5乖离率买入', trend_bias: -0.73
    }, 0);
    test('趋势买点负BIAS', () => contains(negBias, '-0.73%'));

    // 趋势股 + 无BIAS
    const noBias = signalStockCard({
        ...baseStock, trading_system: 'trend',
        trend_buy_type: 'BIAS5乖离率买入'
    }, 0);
    test('趋势买点无BIAS值→不显示BIAS=', () => notContains(noBias, 'BIAS='));

    // 3L股 + buy_point
    const l3Buy = signalStockCard({
        ...baseStock, trading_system: '3l',
        buy_point: '突破买点'
    }, 0);
    test('3L买点显示原有buy_point', () => contains(l3Buy, '突破买点'));

    // 无买点
    const noBuy = signalStockCard({
        ...baseStock, trading_system: '3l',
        buy_point: undefined, trend_buy_type: undefined
    }, 0);
    test('无买点→不显示买点行', () => notContains(noBuy, '买点:'));
}

/* ===================================================== */
/* 第7轮：结论文字测试（关键回归点）                        */
/* ===================================================== */
console.log('\n💡 第7轮：结论文字');
{
    test('趋势股+负BIAS→乖离率买入区', () => {
        const h = signalStockCard({ ...baseStock, trading_system: 'trend', trend_bias: -0.73, stage: '上行' }, 0);
        contains(h, 'BIAS5=-0.73%，价格在EMA5下方，乖离率买入区');
    });
    test('趋势股+BIAS 0-2→逢低吸纳', () => {
        const h = signalStockCard({ ...baseStock, trading_system: 'trend', trend_bias: 1.5, stage: '上行' }, 0);
        contains(h, '价格靠近EMA5，乖离率买入区，可考虑逢低吸纳');
    });
    test('趋势股+BIAS 2-8→持有区', () => {
        const h = signalStockCard({ ...baseStock, trading_system: 'trend', trend_bias: 5.0, stage: '上行' }, 0);
        contains(h, '持有区，趋势健康继续持有');
    });
    test('趋势股+BIAS>8→警戒区', () => {
        const h = signalStockCard({ ...baseStock, trading_system: 'trend', trend_bias: 10.5, stage: '上行' }, 0);
        contains(h, '警戒区，关注回调风险');
    });
    // 3L各阶段结论
    test('buy信号→触发买点结论', () => {
        const h = signalStockCard({ ...baseStock, signal: 'buy', buy_point: '突破买点' }, 0);
        contains(h, '触发突破买点');
    });
    test('缩量整理→中继蓄力', () => {
        const h = signalStockCard({ ...baseStock, stage: '缩量整理', vol_analysis: '缩量' }, 0);
        contains(h, '中继蓄力形态');
    });
    test('上行→趋势健康', () => {
        const h = signalStockCard({ ...baseStock, stage: '上行' }, 0);
        contains(h, '上行趋势健康');
    });
    test('加速→拉升阶段关注卖出信号', () => {
        const h = signalStockCard({ ...baseStock, stage: '加速' }, 0);
        contains(h, '拉升阶段');
        contains(h, '放量滞涨');
    });
    test('滞涨→⚠️', () => {
        const h = signalStockCard({ ...baseStock, stage: '滞涨' }, 0);
        contains(h, '警惕回调');
    });
    test('转弱→⚠️', () => {
        const h = signalStockCard({ ...baseStock, stage: '转弱' }, 0);
        contains(h, '趋势转弱');
    });
    test('区间底部→支撑附近', () => {
        const h = signalStockCard({ ...baseStock, stage: '区间底部' }, 0);
        contains(h, '支撑位');
    });
    test('区间顶部→压力位减仓', () => {
        const h = signalStockCard({ ...baseStock, stage: '区间顶部' }, 0);
        contains(h, '压力位');
        contains(h, '减仓');
    });
    test('区间中段→无明确方向', () => {
        const h = signalStockCard({ ...baseStock, stage: '区间中段' }, 0);
        contains(h, '无明确方向');
    });
}

/* ===================================================== */
/* 第8轮：标签测试                                        */
/* ===================================================== */
console.log('\n🏷️ 第8轮：标签');
{
    const both = signalStockCard({ ...baseStock, profit_model1: true, trend_stock: true }, 0);
    test('盈利1+趋势股→两标签', () => contains(both, '🏆 盈利1', '📈 趋势股'));

    const onlyP = signalStockCard({ ...baseStock, profit_model1: true, trend_stock: false }, 0);
    test('仅盈利1', () => { contains(onlyP, '🏆 盈利1'); notContains(onlyP, '📈 趋势股'); });

    const onlyT = signalStockCard({ ...baseStock, profit_model1: false, trend_stock: true }, 0);
    test('仅趋势股', () => { contains(onlyT, '📈 趋势股'); notContains(onlyT, '🏆 盈利1'); });

    const none = signalStockCard({ ...baseStock, profit_model1: false, trend_stock: false }, 0);
    test('无标签', () => { notContains(none, '🏆'); notContains(none, '趋势股</span>'); });
}

/* ===================================================== */
/* 第9轮：边界条件                                        */
/* ===================================================== */
console.log('\n🧪 第9轮：边界条件');
{
    test('负数涨跌幅→绿色', () => {
        const h = signalStockCard({ ...baseStock, change: -3.5 }, 0);
        contains(h, '-3.5%');
        // 负值颜色是绿色 #44aa44
        contains(h, '#44aa44');
    });
    test('零涨跌幅→红色（默认>=0走红色路径）', () => {
        const h = signalStockCard({ ...baseStock, change: 0 }, 0);
        contains(h, '0%');
        contains(h, '#ff4444');
    });
    test('空对象→不会崩溃', () => {
        const h = signalStockCard({}, 0);
        assert(typeof h === 'string' && h.length > 0);
    });
    test('部分字段缺失→不崩溃', () => {
        const h = signalStockCard({ name: '测试', code: '000001' }, 0);
        contains(h, '测试');
        contains(h, '000001');
        // 缺失字段显示--
        contains(h, '--');
    });
    test('大量数据→渲染不报错', () => {
        for (let i = 0; i < 1000; i++) {
            const h = signalStockCard({ ...baseStock, name: `股票${i}`, code: `${600000 + i}` }, i);
            assert(h.includes(`hchart_${i}`), `第${i}次渲染图表ID不对`);
        }
    });
}

/* ===================================================== */
/* 第10轮：回归测试 — 快照对比                            */
/* ===================================================== */
console.log('\n📸 第10轮：回归快照');
{
    // 典型趋势股（买入区）
    const trendSnapshot = signalStockCard({
        name: '沪硅产业',
        code: '688126',
        price: 25.68,
        change: 3.12,
        sector: '半导体',
        structure: '上涨趋势',
        stage: '上行',
        signal: 'buy',
        trading_system: 'trend',
        trading_reason: '结构上涨趋势+EMA5斜率4.5%+半导体主线方向',
        trend_buy_type: 'BIAS5乖离率买入',
        trend_bias: 1.11,
        vol_analysis: '放量',
        profit_model1: true,
        trend_stock: true,
    }, 0);

    contains(trendSnapshot,
        '沪硅产业', '688126', '25.68', '+3.12%',
        '半导体', '上涨趋势', '上行',
        '🔥趋势交易', '⚡买入',
        '📈', '↑',
        '乖离率买入区', 'BIAS=1.11%',
        '🏆 盈利1', '📈 趋势股',
        'BIAS5=1.11%，乖离率买入区',
        'hchart_0',
        '结构上涨趋势+EMA5斜率4.5%+半导体主线方向',
    );

    // 典型3L股（持有）
    const l3Snapshot = signalStockCard({
        name: '药明康德',
        code: '603259',
        price: 89.45,
        change: -0.85,
        sector: '创新药',
        structure: '上涨趋势',
        stage: '缩量整理',
        signal: 'hold',
        trading_system: '3l',
        buy_point: '突破买点',
        vol_analysis: '缩量',
        profit_model1: false,
        trend_stock: false,
    }, 5);

    contains(l3Snapshot,
        '药明康德', '603259', '89.45',
        '-0.85%', '#44aa44',
        '创新药', '上涨趋势', '缩量整理',
        '📘3L交易', '✅持有',
        '📈', '🔄',
        '突破买点',
        '中继蓄力形态',
        'hchart_5',
    );
    notContains(l3Snapshot, '🏆', '📈 趋势股');

    // 典型卖出信号
    const sellSnapshot = signalStockCard({
        name: '万华化学',
        code: '600309',
        price: 72.30,
        change: -2.15,
        sector: '化工',
        structure: '下降趋势',
        stage: '转弱',
        signal: 'sell',
        trading_system: '3l',
        profit_model1: false,
        trend_stock: false,
    }, 3);

    contains(sellSnapshot,
        '万华化学', '72.30', '-2.15%',
        '下降趋势', '转弱',
        '❌卖出', 'danger',
        '📉', '📉',
        '趋势转弱',
        'hchart_3',
    );
}

/* ===================================================== */
/* 汇总输出                                              */
/* ===================================================== */
const total = pass + fail;
console.log(`\n${'='.repeat(50)}`);
console.log(`  总用例: ${total} | ✅ 通过: ${pass} | ❌ 失败: ${fail}`);
console.log(`${'='.repeat(50)}\n`);

// 保存快照供后续diff比对
const snapshotDir = resolve(__dirname, '../test_snapshots');
mkdirSync(snapshotDir, { recursive: true });
const snapshot = {
    timestamp: new Date().toISOString(),
    total, pass, fail,
    testCounts: { rounds: 10, assertions: total }
};
writeFileSync(`${snapshotDir}/stock_card_snapshot.json`, JSON.stringify(snapshot, null, 2));

process.exit(fail > 0 ? 1 : 0);
