#!/bin/bash
# 全回归测试：后端单元测试 + 功能回测 + 前端 E2E
set -e

cd /home/ubuntu/3l-server

echo "╔═══════════════════════════════════════════════╗"
echo "║          🔄  全 回 归 测 试                   ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

START=$(date +%s)

# =========================================
# 第1步：后端单元测试（含 API 测试 + 复盘流程测试）
# =========================================
echo ""
echo "━━━ 第1步：后端单元测试（含API/复盘流程） ━━━"
echo ""

python3 -m pytest tests/ -v --tb=short && PYTEST_OK=1 || PYTEST_OK=0

echo ""
echo "  ── 其中 API 接口测试 ──"
python3 -m pytest tests/test_api.py -q --tb=short 2>&1 | tail -3
echo ""
echo "  ── 复盘流程测试 ──"
python3 -m pytest tests/test_review_flow.py -q --tb=short 2>&1 | tail -3

echo ""
if [ "$PYTEST_OK" -eq 1 ]; then
    echo "  ✅ 后端单元测试通过"
else
    echo "  ❌ 后端单元测试有失败"
fi

# =========================================
# 第2步：功能回测
# =========================================
echo ""
echo "━━━ 第2步：功能回测（德明利3L） ━━━"
echo ""

python3 scripts/test_demingli_3l.py 2>&1 | tail -5 && BACKTEST_OK=1 || BACKTEST_OK=0

echo ""
if [ "$BACKTEST_OK" -eq 1 ]; then
    echo "  ✅ 功能回测通过"
else
    echo "  ❌ 功能回测有失败"
fi

# =========================================
# 第3步：前端 E2E
# =========================================
echo ""
echo "━━━ 第3步：前端 E2E 测试 ━━━"
echo ""

# 确保 server 在运行
if ! curl -s -o /dev/null -w '' http://localhost:8080/ 2>/dev/null; then
    echo "  ⚠️  3L Server 未运行，跳过前端 E2E"
    E2E_OK=0
else
    node tests/frontend_e2e.mjs && E2E_OK=1 || E2E_OK=0
fi

echo ""
if [ "$E2E_OK" -eq 1 ]; then
    echo "  ✅ 前端 E2E 测试通过"
else
    echo "  ❌ 前端 E2E 测试有失败"
fi

# =========================================
# 第4步：前端 stock_card 单元测试
# =========================================
echo ""
echo "━━━ 第4步：stock_card 单元测试 ━━━"
echo ""

node tests/test_stock_card.mjs 2>&1 | tail -5 && SC_OK=1 || SC_OK=0

echo ""
if [ "$SC_OK" -eq 1 ]; then
    echo "  ✅ stock_card 测试通过"
else
    echo "  ❌ stock_card 测试有失败"
fi

# =========================================
# 汇总
# =========================================
END=$(date +%s)
DURATION=$((END - START))

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║          全回归测试报告                        ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""
printf "  🧪 后端单元测试  : %s\n" $([ "$PYTEST_OK" -eq 1 ] && echo "✅ 通过" || echo "❌ 有失败")
printf "  📊 功能回测      : %s\n" $([ "$BACKTEST_OK" -eq 1 ] && echo "✅ 通过" || echo "❌ 有失败")
printf "  🌐 前端 E2E      : %s\n" $([ "$E2E_OK" -eq 1 ] && echo "✅ 通过" || echo "❌ 有失败")
printf "  🃏 stock_card    : %s\n" $([ "$SC_OK" -eq 1 ] && echo "✅ 通过" || echo "❌ 有失败")
echo ""
echo "  ⏱  耗时: ${DURATION}秒"
echo ""

ALL_OK=$((PYTEST_OK && BACKTEST_OK && E2E_OK && SC_OK))
if [ "$ALL_OK" -eq 1 ]; then
    echo "  🎉 全回归全部通过！"
    exit 0
else
    echo "  ⚠️  请检查上面的失败项"
    exit 1
fi
