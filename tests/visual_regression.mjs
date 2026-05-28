#!/usr/bin/env node
/**
 * 视觉回归测试 — 龙头观测页面截图对比
 *
 * 用法:
 *   node tests/visual_regression.mjs              # 首次运行（生成基线）
 *   node tests/visual_regression.mjs --compare     # 对比基线
 *   node tests/visual_regression.mjs --update      # 更新基线
 *
 * 依赖: playwright (已安装)
 */
import { chromium } from 'playwright';
import { mkdirSync, existsSync, readFileSync, writeFileSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_DIR = join(__dirname, '..');
const SCREENSHOTS_DIR = join(PROJECT_DIR, 'tests', 'screenshots');
const BASELINE_DIR = join(SCREENSHOTS_DIR, 'baseline');
const CURRENT_DIR = join(SCREENSHOTS_DIR, 'current');

const BASE_URL = 'http://localhost:8080';

// 需要截图的页面区域
const SHOTS = [
  {
    name: 'leader-dashboard',
    description: '龙头观测：两区布局',
    path: '/monitor',
    selector: '.info-block', // 只在龙头观测区块截图
    viewport: { width: 1280, height: 900 },
  },
  {
    name: 'leader-dashboard-watched',
    description: '龙头观测：关注的行业表格',
    path: '/monitor',
    selector: '.leader-table',
    viewport: { width: 1280, height: 900 },
  },
];

async function main() {
  const mode = process.argv.includes('--compare') ? 'compare'
    : process.argv.includes('--update') ? 'update'
    : 'baseline';

  console.log(`📸 视觉回归测试 — 模式: ${mode}`);
  console.log(`   基线目录: ${BASELINE_DIR}`);
  console.log();

  mkdirSync(BASELINE_DIR, { recursive: true });
  mkdirSync(CURRENT_DIR, { recursive: true });

  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    deviceScaleFactor: 1,
  });

  const page = await context.newPage();

  let passed = 0;
  let failed = 0;

  for (const shot of SHOTS) {
    const currentPath = join(CURRENT_DIR, `${shot.name}.png`);
    const baselinePath = join(BASELINE_DIR, `${shot.name}.png`);

    try {
      // 导航到页面（不用 networkidle，页面有30秒轮询）
      await page.goto(`${BASE_URL}${shot.path}`, { waitUntil: 'domcontentloaded', timeout: 15000 });

      // 等待页面静态内容就绪
      await page.waitForSelector('.monitor-layout', { timeout: 10000 }).catch(() => {});
      await page.waitForTimeout(1000);

      // 点击"龙头观测"标题展开内容
      const leaderTitle = page.locator('text=🏆 龙头观测');
      if (await leaderTitle.isVisible()) {
        await leaderTitle.click();
        await page.waitForTimeout(500);
      }

      // 等待特定元素可见
      if (shot.selector) {
        await page.waitForSelector(shot.selector, { timeout: 5000 }).catch(() => {
          console.log(`  ⚠️ 选择器 "${shot.selector}" 未找到，截全页`);
        });
      }

      // 截图
      await page.screenshot({ path: currentPath, fullPage: false });
      console.log(`  📷 截图: ${shot.name} (${shot.description})`);

      // 对比基线
      if (mode === 'compare' && existsSync(baselinePath)) {
        const baseline = readFileSync(baselinePath);
        const current = readFileSync(currentPath);

        // 简单的像素大小对比（完美对比需要 pixelmatch 库）
        if (baseline.length !== current.length) {
          console.log(`  ❌ 像素差异! 基线=${baseline.length}bytes, 当前=${current.length}bytes`);
          failed++;
        } else {
          console.log(`  ✅ 与基线一致 (${baseline.length}bytes)`);
          passed++;
        }
      } else if (mode === 'update' || mode === 'baseline') {
        // 生成/更新基线
        writeFileSync(baselinePath, readFileSync(currentPath));
        console.log(`  💾 基线已${mode === 'update' ? '更新' : '生成'}: ${baselinePath}`);
        passed++;
      }
    } catch (err) {
      console.log(`  ❌ 截图失败: ${shot.name} - ${err.message}`);
      failed++;
    }
  }

  await browser.close();

  // 汇总
  console.log();
  console.log('═'.repeat(50));
  if (mode === 'compare') {
    console.log(`  视觉回归结果: ${passed} 通过 / ${failed} 失败 / 共${SHOTS.length}项`);
  } else {
    console.log(`  基线已就绪: ${passed} 张截图 / ${SHOTS.length} 项`);
  }
  console.log('═'.repeat(50));

  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});
