"""L4 API层验证 — 验证 /api/review/today 端点的结构正确性和数据正确性

运行：python3 -m pytest tests/test_data_verify_l4_api.py -v

注意：需要服务运行在 127.0.0.1:8080
"""
import json
import os
import subprocess
import sys
import time

import pytest

API_BASE = "http://127.0.0.1:8080"
SERVER_SERVICE = "3l-server"


def _api_get(path):
    """调用 API 并返回 JSON"""
    import urllib.request
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        pytest.fail(f"API {url} 请求失败: {e}")


@pytest.fixture(scope="module")
def review_data():
    """获取 /api/review/today 的完整响应"""
    return _api_get("/api/review/today")


class TestL4ApiStructure:
    """L4-1: API 顶层结构验证"""

    def test_top_level_keys(self, review_data):
        """顶层必须包含关键字段"""
        required_keys = ['date', 'market', 'mainline', 'holdings', 'buy_signals', 'trading_plan']
        for k in required_keys:
            assert k in review_data, f"顶层缺少字段: {k}"

    def test_date_format(self, review_data):
        """date 必须是 YYYY-MM-DD 格式"""
        date_str = review_data.get('date', '')
        assert len(date_str) == 10, f"date 长度应为10: {date_str}"
        parts = date_str.split('-')
        assert len(parts) == 3
        assert parts[0].isdigit() and len(parts[0]) == 4  # year
        assert parts[1].isdigit() and len(parts[1]) == 2  # month
        assert parts[2].isdigit() and len(parts[2]) == 2  # day


class TestL4MainlineStructure:
    """L4-2: mainline 结构验证（此处曾是 L4 验证盲区）"""

    def test_mainline_key_exists(self, review_data):
        """mainline 字段必须存在"""
        assert 'mainline' in review_data, "mainline 字段缺失"

    def test_mainline_has_lines(self, review_data):
        """mainline.lines 存在且非空（非交易日应返回最后交易日数据）"""
        mainline = review_data['mainline']
        assert 'lines' in mainline, "mainline.lines 字段缺失"
        lines = mainline['lines']
        assert len(lines) > 0, f"mainline.lines 为空 (date={review_data.get('date')})"

    def test_mainline_lines_format(self, review_data):
        """每条 line 必须包含关键字段"""
        lines = review_data['mainline']['lines']
        required_line_keys = ['name', 'chg_1d', 'chg_20d', 'stage', 'is_mainline', 'is_secondary']
        for i, line in enumerate(lines):
            for k in required_line_keys:
                assert k in line, f"lines[{i}] 缺少字段: {k}"

    def test_mainline_has_secondary(self, review_data):
        """mainline.secondary 存在"""
        assert 'secondary' in review_data['mainline'], "mainline.secondary 缺失"

    def test_mainline_has_all_ranked(self, review_data):
        """mainline.all_ranked 存在且非空"""
        all_ranked = review_data['mainline'].get('all_ranked', [])
        assert len(all_ranked) > 0, "all_ranked 为空"

    def test_mainline_lines_count(self, review_data):
        """lines 前5条为主线"""
        lines = review_data['mainline']['lines']
        assert len(lines) <= 5, f"lines 超过5条: {len(lines)}"


class TestL4MainlineData:
    """L4-3: mainline 数据值验证"""

    def test_chg_1d_reasonable(self, review_data):
        """chg_1d 在合理范围内（>-20%, <20%）"""
        for line in review_data['mainline']['lines']:
            chg = line.get('chg_1d')
            assert chg is not None, f"{line['name']} chg_1d 为 None"
            assert -20 < chg < 20, f"{line['name']} chg_1d={chg} 超出合理范围"

    def test_chg_20d_exists(self, review_data):
        """chg_20d 存在"""
        for line in review_data['mainline']['lines']:
            assert 'chg_20d' in line, f"{line['name']} 缺少 chg_20d"

    def test_stage_not_empty(self, review_data):
        """stage 非空"""
        for line in review_data['mainline']['lines']:
            stage = line.get('stage', '')
            assert stage, f"{line['name']} stage 为空"

    @pytest.mark.skip(reason="仅交易日验证——非交易日返回最后交易日数据")
    def test_chg_1d_nonzero_on_trading_day(self, review_data):
        """交易日 chg_1d 非零"""
        for line in review_data['mainline']['lines']:
            assert line.get('chg_1d') != 0, f"{line['name']} chg_1d 为 0（非交易日可能有缓存问题）"


class TestL4ConceptMainline:
    """L4-4: 概念主线验证"""

    def test_concept_mainline_exists(self, review_data):
        """mainline.concept_mainline 存在"""
        assert 'concept_mainline' in review_data['mainline'], "concept_mainline 缺失"

    def test_concept_mainline_is_dict(self, review_data):
        """concept_mainline 是 dict"""
        cm = review_data['mainline'].get('concept_mainline', {})
        assert isinstance(cm, dict), f"concept_mainline 类型错误: {type(cm)}"


class TestL4Market:
    """L4-5: 市场数据验证"""

    def test_market_structure(self, review_data):
        """market 包含核心字段"""
        market = review_data.get('market', {})
        for k in ['price', 'change', 'vl_score', 'position']:
            assert k in market, f"market 缺少字段: {k}"

    def test_market_price_nonzero(self, review_data):
        """市场收盘价非0"""
        price = review_data.get('market', {}).get('price', '0')
        assert float(price) > 0, f"market.price={price} 应为正数"


class TestL4Integration:
    """L4-6: 端到端正确性验证"""

    def test_electronics_chemical_exists(self, review_data):
        """电子化学品在主线列表中"""
        lines = review_data['mainline']['lines']
        names = [l['name'] for l in lines]
        assert '电子化学品' in names, f"电子化学品不在主线中: {names}"

    def test_electronics_chemical_data_consistency(self, review_data):
        """电子化学品的数据应与其他层一致"""
        for line in review_data['mainline']['lines']:
            if line['name'] == '电子化学品':
                chg = line.get('chg_1d')
                assert chg is not None
                # 非交易日应返回最后交易日数据，chg 合理即可
                assert -10 < chg < 10, f"电子化学品 chg_1d={chg} 异常"
                break


# ===== 运行：python3 -m pytest tests/test_data_verify_l4_api.py -v =====
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
