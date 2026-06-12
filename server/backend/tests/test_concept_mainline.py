"""概念主线测试 — _get_mainline_level 单元测试 + get_stock_card dict 透传

测试策略：
1. _get_mainline_level 直接测试（不依赖外部数据，6种场景全面覆盖）
2. get_stock_card 传 dict main_lines 验证数据透传不丢失（不依赖概念映射）
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
import pytest


# ═══════════════════════════════════════════════
# 测试1: _get_mainline_level 概念主线判定（纯单元测试，无外部依赖）
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
            sector='元件',
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
# 测试2: get_stock_card dict main_lines 透传
# ═══════════════════════════════════════════════

class TestGetStockCardConceptDict:

    @staticmethod
    def _make_fake_klines(n=31):
        return [
            {'date': f'202605{i:02d}', 'open': 70, 'high': 71,
             'low': 69, 'close': 70, 'volume': 100}
            for i in range(1, n + 1)
        ]

    def test_dict_main_lines_returns_card_with_mainline_level(self):
        """main_lines 传 dict（含 concept_mainline）→ 正常返回卡片"""
        card = get_stock_card(
            code='601138',
            date_str='20260531',
            main_lines={
                'lines': [{'name': '元件'}],
                'secondary': [{'name': '半导体'}],
                'concept_mainline': {
                    'lines': [{'name': '英伟达概念'}],
                    'secondary': [{'name': '存储芯片'}],
                },
            },
            direction='消费电子',
            klines=self._make_fake_klines(),
        )
        assert card is not None
        assert card.get('sector') == '消费电子'
        # mainline_level 必须存在（值依赖概念映射数据，不做硬断言）
        assert card.get('mainline_level', '__MISSING__') != '__MISSING__'

    def test_list_mainlines_also_works(self):
        """main_lines 传纯 list 兼容旧模式"""
        card = get_stock_card(
            code='601138',
            date_str='20260531',
            main_lines=['元件', '电子化学品'],
            direction='消费电子',
            klines=self._make_fake_klines(),
        )
        assert card is not None
        assert card.get('mainline_level', '__MISSING__') != '__MISSING__'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
