#!/bin/bash
# ============================================
# 生成彩色白底PDF（WeChat友好版）
# 用法:
#   ./scripts/generate_wechat_pdf.sh input.md [output.pdf]
#
# 默认输出: docs/<input-basename>.pdf
# 模板: docs/wechat-pdf-template.html (彩色白底卡片风格)
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$SCRIPT_DIR/docs/wechat-pdf-template.html"
INPUT_MD="$1"
OUTPUT_PDF="$2"

if [ -z "$INPUT_MD" ]; then
    echo "❌ 用法: $0 input.md [output.pdf]"
    echo "示例: $0 docs/panic-analysis-corrected.md"
    exit 1
fi

if [ ! -f "$INPUT_MD" ]; then
    echo "❌ 找不到输入文件: $INPUT_MD"
    exit 1
fi

if [ ! -f "$TEMPLATE" ]; then
    echo "❌ 找不到模板: $TEMPLATE"
    exit 1
fi

if [ -z "$OUTPUT_PDF" ]; then
    BASENAME=$(basename "$INPUT_MD" .md)
    OUTPUT_PDF="$(dirname "$INPUT_MD")/${BASENAME}.pdf"
fi

TITLE=$(head -1 "$INPUT_MD" | sed 's/^# *//; s/ *$//')
TEMPDIR=$(mktemp -d)
HTML_FILE="$TEMPDIR/output.html"

echo "📄 生成PDF..."
echo "  输入: $INPUT_MD"
echo "  输出: $OUTPUT_PDF"
echo "  标题: $TITLE"
echo "  模板: $TEMPLATE"

# Step 1: Markdown → HTML (用彩色白底模板)
pandoc -f markdown -t html5 \
    --template="$TEMPLATE" \
    --metadata title="$TITLE" \
    "$INPUT_MD" > "$HTML_FILE"

# Step 2: HTML → PDF (wkhtmltopdf)
wkhtmltopdf \
    --encoding utf-8 \
    --enable-local-file-access \
    --page-size A4 \
    --margin-top 12mm \
    --margin-bottom 12mm \
    --margin-left 10mm \
    --margin-right 10mm \
    "$HTML_FILE" "$OUTPUT_PDF" 2>/dev/null

rm -rf "$TEMPDIR"

echo "✅ PDF已生成: $OUTPUT_PDF ($(du -h "$OUTPUT_PDF" | cut -f1))"
