/**
 * 前端 E2E 回归测试
 * 打开关键页面 → 截图 + 检查JS报错 + 关键元素存在性
 *
 * 用法: node tests/frontend_e2e.mjs [base_url]
 * 默认 base_url = http://localhost:8080
 */

import { chromium } from 'playwright';
import { strict as assert } from 'node:assert';
import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const BASE_URL = process.argv[2] || 'http://localhost:8080';
const SCREENSHOT_DIR = resolve(__dirname, '../test_snapshots');

let pass = 0, fail = 0;
const errors = [];

function ok(name) { pass++; console.log(`  ✅ ${name}`); }
function ng(name, msg) { fail++; errors.push({ name, message: msg }); console.log(`  ❌ ${name}: ${msg}`); }

async function testPage(browser, name, path, checks, opts = {}) {
    const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await context.newPage();
    const consoleErrors = [];
    const { waitUntil = 'networkidle' } = opts;

    page.on('console', msg => {
        if (msg.type() === 'error') {
            const text = msg.text();
            // 过滤资源加载失败（数据未缓存时的正常现象）
            if (!text.includes('ERR_EMPTY_RESPONSE') && !text.includes('Failed to load resource')) {
                consoleErrors.push(text);
            }
        }
    });
    page.on('pageerror', err => consoleErrors.push(err.message));

    try {
        await page.goto(`${BASE_URL}${path}`, { waitUntil, timeout: 20000 });
        await page.waitForTimeout(1000);
        await page.screenshot({ path: `${SCREENSHOT_DIR}/${name}.png`, fullPage: true });

        if (consoleErrors.length === 0) {
            ok(`${name}: 无JS报错`);
        } else {
            ng(`${name}: 无JS报错`, `发现 ${consoleErrors.length} 个:\n${consoleErrors.join('\n')}`);
        }

        for (const [checkName, checkFn] of Object.entries(checks || {})) {
            try { await checkFn(page); ok(`${name}: ${checkName}`); }
            catch (e) { ng(`${name}: ${checkName}`, e.message); }
        }
    } catch (e) {
        ng(`${name}: 页面加载`, e.message.slice(0, 200));
    } finally {
        await context.close();
    }
}

// ============ 检查工厂 ============
const exists = (sel) => async (page) => {
    const count = await page.locator(sel).count();
    assert(count > 0, `找不到 "${sel}"`);
};
const minCount = (sel, n) => async (page) => {
    const count = await page.locator(sel).count();
    assert(count >= n, `"${sel}" 只有 ${count} 个, 预期 >= ${n}`);
};
const bodyOk = async (page) => {
    const text = await page.locator('body').textContent();
    assert(text.trim().length > 0, 'body为空');
};

// ============ 运行 ============
async function main() {
    mkdirSync(SCREENSHOT_DIR, { recursive: true });
    console.log(`🌐 前端 E2E 回归测试: ${BASE_URL}\n`);

    const browser = await chromium.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    // 1. 首页
    await testPage(browser, 'index', '/index.html', {
        'body有内容': bodyOk,
    });

    // 2. 每日复盘
    await testPage(browser, 'review', '/review.html', {
        '有section区域': minCount('.section', 1),
        '有标题': exists('.section-title'),
    });

    // 3. 盘中盯盘（有持续数据轮询，用 domcontentloaded）
    await testPage(browser, 'monitor', '/monitor.html', {
        '盘面概览': exists('.quote-grid, .quote-item'),
        '板块排行': exists('.sector-panel, .leader-table'),
        '信号表格': exists('.signal-table'),
    }, { waitUntil: 'domcontentloaded' });

    // 4. 自选股
    await testPage(browser, 'watchlist', '/watchlist.html', {
        '方向Tab': exists('.dir-tabs, .dir-tab'),
        '搜索框': exists('input.search-input, input[type="text"]'),
        '自选股列表': minCount('.cards-area > *, .stock-card, .signal-stock-card, .dir-tab', 1),
    });

    // 5. 趋势候选（分页只有多页时才渲染）
    await testPage(browser, 'trend_candidates', '/trend_candidates.html', {
        '主Tab': exists('.main-tabs, .main-tab'),
        '行业子Tab': exists('.ind-tabs-wrap, .ind-tab'),
        '个股卡片区域': exists('.cards-area'),
    });

    // 6. 个股分析
    await testPage(browser, 'stock_analysis', '/stock_analysis.html', {
        '搜索框': exists('input[type="text"]'),
    });

    // 7. 宏观
    await testPage(browser, 'macro', '/macro.html', {
        '页面加载': bodyOk,
    });

    // 8. 涨幅榜
    await testPage(browser, 'top_gainers', '/top_gainers.html', {
        '页面加载': bodyOk,
    });

    await browser.close();

    // 汇总
    const total = pass + fail;
    console.log(`\n${'='.repeat(50)}`);
    console.log(`  前端 E2E: ${total} 项 | ✅ ${pass} | ❌ ${fail}`);
    console.log(`${'='.repeat(50)}`);

    writeFileSync(`${SCREENSHOT_DIR}/e2e_report.json`, JSON.stringify({
        timestamp: new Date().toISOString(), total, pass, fail, errors,
    }, null, 2));

    console.log(`\n📸 截图: ${SCREENSHOT_DIR}/`);
    process.exit(fail > 0 ? 1 : 0);
}

main().catch(e => { console.error('崩溃:', e.message); process.exit(1); });
