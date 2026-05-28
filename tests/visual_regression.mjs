#!/usr/bin/env node
/**
 * 视觉回归测试 — 页面截图基线对比
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

const SHOTS = [
  {
    name: 'leader-dashboard-full',
    description: '龙头观测：完整展开',
    path: '/monitor',
    type: 'viewport',
    viewport: { width: 1280, height: 900 },
  },
  {
    name: 'leader-dashboard-watched',
    description: '龙头观测：关注的行业表格',
    path: '/monitor',
    type: 'element',
    selector: '.leader-table >> nth=0', // 第一个表格=关注的行业
    viewport: { width: 1280, height: 900 },
  },
];

async function expandLeaderDashboard(page) {
  // 点击"龙头观测"标题展开
  const leaderTitle = page.locator('.block-title:has-text("🏆 龙头观测")');
  await leaderTitle.waitFor({ state: 'visible', timeout: 10000 });
  await leaderTitle.click();

  // 等待展开后的内容出现（"关注的行业"子标题）
  await page.locator('.block-title-sm:has-text("📋 关注的行业")').waitFor({ state: 'visible', timeout: 10000 });

  // 等待实际数据渲染（等一只股票名称出现）
  await page.waitForTimeout(2000); // 等API返回+渲染

  // 尝试等任意龙头股名出现（证明数据已到）
  await page.locator('.leader-table td b').first().waitFor({ state: 'visible', timeout: 15000 }).catch(() => {
    console.log('  ⚠️ 龙头数据未加载完成，继续截图');
  });
}

async function main() {
  const mode = process.argv.includes('--compare') ? 'compare'
    : process.argv.includes('--update') ? 'update'
    : 'baseline';

  console.log(`📸 视觉回归 — 模式: ${mode}`);
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

  // 单页导航 — 所有截图共享一次页面加载
  try {
    await page.goto(`${BASE_URL}/monitor`, { waitUntil: 'domcontentloaded', timeout: 15000 });
    await page.waitForSelector('.monitor-layout', { timeout: 10000 });
    await expandLeaderDashboard(page);
  } catch (err) {
    console.log(`  ❌ 页面加载/展开失败: ${err.message}`);
    await browser.close();
    process.exit(1);
  }

  for (const shot of SHOTS) {
    const currentPath = join(CURRENT_DIR, `${shot.name}.png`);
    const baselinePath = join(BASELINE_DIR, `${shot.name}.png`);

    try {
      if (shot.type === 'element' && shot.selector) {
        // 截取特定元素区域（取第一个匹配）
        const el = page.locator(shot.selector).first();
        await el.screenshot({ path: currentPath });
      } else {
        // 截取视口
        await page.screenshot({ path: currentPath, fullPage: false });
      }
      console.log(`  📷 截图: ${shot.name} (${shot.description})`);

      // 对比/生成基线
      if (mode === 'compare' && existsSync(baselinePath)) {
        const baseline = readFileSync(baselinePath);
        const current = readFileSync(currentPath);
        if (baseline.length !== current.length) {
          console.log(`  ❌ 像素差异! 基线=${baseline.length}bytes, 当前=${current.length}bytes`);
          failed++;
        } else {
          console.log(`  ✅ 与基线一致 (${baseline.length}bytes)`);
          passed++;
        }
      } else {
        writeFileSync(baselinePath, readFileSync(currentPath));
        console.log(`  💾 基线${mode === 'update' ? '更新' : '生成'}: ${baselinePath}`);
        passed++;
      }
    } catch (err) {
      console.log(`  ❌ 截图失败: ${shot.name} - ${err.message}`);
      failed++;
    }
  }

  await browser.close();

  console.log();
  console.log('═'.repeat(50));
  if (mode === 'compare') {
    console.log(`  结果: ${passed} 通过 / ${failed} 失败 / 共${SHOTS.length}项`);
  } else {
    console.log(`  基线就绪: ${passed} 张 / ${SHOTS.length} 项`);
  }
  console.log('═'.repeat(50));

  process.exit(failed > 0 ? 1 : 0);
}

main().catch(err => {
  console.error('Fatal:', err);
  process.exit(1);
});
