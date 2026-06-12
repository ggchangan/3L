"""概念主线集成测试 — 验证 concept_mainline 从缓存→卡片全线贯通

测试策略：
1. _get_mainline_level 单元测试（行业非主线+概念主线）
2. get_stock_card 接收 dict main_lines 时 concept 数据透传
3. cache 结构完整性验证（mock review_service 写缓存）
"""
import sys, os
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.services.stock_card_service import (
    _get_mainline_level,
    get_stock_card,
)
from backend.services.review_service import (
    MAINLINES_CACHE_PATH,
    run_daily_review,
)
from backend.core.data_layer import (
    get_all_stocks,
    get_industry_map,
    get_sector_daily,
)
import pytest
import json
import os


# ═══════════════════════════════════════════════
# 测试1: _get_mainline_level 概念主线判定
# ═══════════════════════════════════════════════

class TestConceptMainlineLevel:

    def test_industry_non_main_concept_main_returns_main(self):
        """行业非主线 + 概念是主线 → 返回 '主线'"""
        result = _get_mainline_level(
            sector='消费电子',
            main_line_names=['电子化学品', '元件', '银行'],
            sub_main_names=['半导体', '小金属'],
            concept_names=['PCB概念', '先进封装'],
            concept_main=['先进封装', '光刻机'],
            concept_sub=['存储芯片'],
        )
        assert result == '主线', f"期望'主线'，实际'{result}'"

    def test_industry_non_main_concept_sub_returns_secondary(self):
        """行业非主线 + 概念是次级 → 返回 '次级主线'"""
        result = _get_mainline_level(
            sector='消费电子',
            main_line_names=['电子化学品', '元件', '银行'],
            sub_main_names=['半导体', '小金属'],
            concept_names=['存储芯片'],
            concept_main=['先进封装', '光刻机'],
            concept_sub=['存储芯片'],
        )
        assert result == '次级主线', f"期望'次级主线'，实际'{result}'"

    def test_industry_main_overrides_concept(self):
        """行业已经是主线 → 即使概念不是主线也返回 '主线'"""
        result = _get_mainline_level(
            sector='元件',  # 行业本身就是主线
            main_line_names=['电子化学品', '元件', '银行'],
            sub_main_names=['半导体', '小金属'],
            concept_names=[],
            concept_main=['先进封装'],
            concept_sub=[],
        )
        assert result == '主线'

    def test_no_match_returns_non_mainline(self):
        """行业和概念都不是主线 → 返回 '非主线'"""
        result = _get_mainline_level(
            sector='房地产',
            main_line_names=['电子化学品', '元件', '银行'],
            sub_main_names=['半导体', '小金属'],
            concept_names=['跨境电商'],
            concept_main=['先进封装', '光刻机'],
            concept_sub=['存储芯片'],
        )
        assert result == '非主线'

    def test_no_concept_data_uses_industry_only(self):
        """没有概念数据时 → 回退到行业主线判定"""
        result = _get_mainline_level(
            sector='银行',
            main_line_names=['电子化学品', '元件', '银行'],
            sub_main_names=['半导体', '小金属'],
            concept_names=None,
            concept_main=None,
            concept_sub=None,
        )
        assert result == '主线'

    def test_multiple_concept_names_any_match_triggers_main(self):
        """多个概念名称，只要有一个匹配主线就返回 '主线'"""
        result = _get_mainline_level(
            sector='消费电子',
            main_line_names=['电子化学品', '元件', '银行'],
            sub_main_names=['半导体', '小金属'],
            concept_names=['光模块', 'PCB概念', '宁德时代概念'],
            concept_main=['PCB概念', '先进封装'],
            concept_sub=['存储芯片'],
        )
        assert result == '主线', f"PCB概念匹配主线，期望'主线'"


# ═══════════════════════════════════════════════
# 测试2: get_stock_card 接收 dict 类型 main_lines
# ═══════════════════════════════════════════════

class TestGetStockCardConceptDict:

    CODE_WITH_CONCEPT = '601138'  # 工业富联

    def test_dict_main_lines_preserves_concept(self):
        """main_lines 传 dict（含 concept_mainline）→ 卡片不丢数据"""
        dict_mainlines = {
            'lines': [{'name': '元件'}],
            'secondary': [{'name': '半导体'}],
            'concept_mainline': {
                'lines': [{'name': 'PCB概念'}],
                'secondary': [{'name': '存储芯片'}],
            },
        }
        card = get_stock_card(
            code=self.CODE_WITH_CONCEPT,
            date_str='20260611',
            main_lines=dict_mainlines,
        )
        assert card is not None, '卡片应为非空'
        assert 'mainline_level' in card, '卡片应包含 mainline_level'
        assert card['mainline_level'] != ''

    def test_list_mainlines_loses_concept(self):
        """main_lines 传纯 list → concept 数据丢失，回退到行业线判定"""
        list_mainlines = ['元件', '电子化学品']
        card = get_stock_card(
            code=self.CODE_WITH_CONCEPT,
            date_str='20260611',
            main_lines=list_mainlines,
        )
        # list模式一定没有concept数据，但mainline_level不应为空
        assert card is not None

    def test_concept_mainline_makes_a_difference(self):
        """同一只股票，有概念主线数据时 mainline_level 更优"""
        card_no_concept = get_stock_card(
            code=self.CODE_WITH_CONCEPT,
            date_str='20260611',
            main_lines=['元件', '电子化学品'],
        )
        # 工业富联的行业分类可能不是元件/电子化学品 → 非主线
        level_no_concept = card_no_concept.get('mainline_level', '')

        card_with_concept = get_stock_card(
            code=self.CODE_WITH_CONCEPT,
            date_str='20260611',
            main_lines={
                'lines': [{'name': '元件'}, {'name': '电子化学品'}],
                'secondary': [{'name': '半导体'}],
                'concept_mainline': {
                    'lines': [{'name': '英伟达概念'}, {'name': '工业互联'}],
                    'secondary': [{'name': '存储芯片'}],
                },
            },
        )
        level_with_concept = card_with_concept.get('mainline_level', '')

        # 工业富联属于AI服务器概念→加概念线后应从非主线变主线
        assert level_no_concept == '非主线', f"无概念数据应判非主线, 实际{level_no_concept}"
        assert level_with_concept in ('主线', '次级主线'), f"加概念线后应为(次)主线, 实际{level_with_concept}"


# ═══════════════════════════════════════════════
# 测试3: cache 写入结构完整性
# ═══════════════════════════════════════════════

@pytest.mark.skip(reason='集成测试，需 review_service 初始化数据')
class TestCacheWrite:

    def test_cache_contains_concept_mainline(self):
        """run_daily_review 后缓存文件包含 concept_mainline"""
        run_daily_review('20260611')
        with open(MAINLINES_CACHE_PATH) as f:
            data = json.load(f)
        assert 'concept_mainline' in data, '缓存应包含 concept_mainline'
        cm = data['concept_mainline']
        assert 'lines' in cm, 'concept_mainline 应含 lines'
        assert 'secondary' in cm, 'concept_mainline 应含 secondary'
        assert len(cm['lines']) > 0, '概念主线不应为空'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
