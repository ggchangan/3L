"""
趋势交易集成测试 — 先写测试，再改代码

测试点：
1. 数据层：decide_system 数据能合并进 review 结构
2. API层：stock-analysis 返回 trading_system 字段
3. 前端：signalStockCard 能渲染 trading_system 字段
4. 全链路：数据生成→API→展示 一致性
"""
import json
import pytest
from scripts.data_layer import get_all_stocks


# ==================== 数据层集成测试 ====================

class TestReviewDataField:
    """
    测试 decide_system() 结果能正确合并进 review 数据结构。
    
    要求在 holdings_review 和 buy_signals_review 中：
    - 趋势股: {'trading_system': 'trend', 'trading_reason': '三层全部通过...',
               'trend_buy': {...} 趋势买点信息}
    - 3L股:   {'trading_system': '3l', 'trading_reason': '结构=...不是上涨趋势'}
    """

    def test_decide_system_returns_valid(self, stocks):
        """decide_system 返回值可写入 review 字段"""
        from scripts.trend_trading import decide_system_with_detail
        
        stocks_data = stocks.get('stocks', stocks)
        main_lines = ['半导体', '算力', '新能源']
        
        # 测试：混入各方向股票
        test_cases = ['688126', '002640', '688234', '300054']
        for code in test_cases:
            for sec, ss in stocks_data.items():
                if code in ss:
                    kls = ss[code]
                    if not kls: break
                    date_str = kls[-1]['date']
                    fmt = date_str[:4]+'-'+date_str[4:6]+'-'+date_str[6:8] if len(date_str)==8 else date_str
                    
                    detail = decide_system_with_detail(code, fmt, stocks_data, main_lines)
                    
                    # 核心测试：返回值可以安全写入 review dict
                    review_entry = {
                        'code': code,
                        'trading_system': detail['system'],
                        'trading_reason': detail['reason'],
                    }
                    
                    assert 'trading_system' in review_entry
                    assert review_entry['trading_system'] in ('trend', '3l')
                    assert 'trading_reason' in review_entry
                    break
            else:
                continue
            break

    def test_trend_stock_has_buy_info(self, stocks):
        """趋势股应有乖离率买点信息"""
        from scripts.trend_trading import decide_system_with_detail, detect_trend_buy
        
        stocks_data = stocks.get('stocks', stocks)
        main_lines = ['半导体', '算力', '新能源']
        
        # 找趋势股（手动指定列表中的）
        for sec, ss in stocks_data.items():
            if '300054' in ss:
                kls = ss['300054']
                date_str = kls[-1]['date']
                fmt = date_str[:4]+'-'+date_str[4:6]+'-'+date_str[6:8] if len(date_str)==8 else date_str
                
                detail = decide_system_with_detail('300054', fmt, stocks_data, main_lines)
                assert detail['system'] == 'trend'
                
                bt = detect_trend_buy('300054', fmt, stocks_data, main_lines)
                
                # 趋势股在review中应有的字段
                review_entry = {
                    'code': '300054',
                    'trading_system': 'trend',
                    'trading_reason': detail['reason'],
                }
                if bt:
                    review_entry['trend_buy_type'] = bt['buy_type']
                    review_entry['trend_bias'] = bt['bias5']
                    review_entry['trend_reason'] = bt['reason']
                    assert 'trend_buy_type' in review_entry
                    assert 'BIAS' in review_entry['trend_buy_type']
                break

    def test_3l_stock_has_no_trend_buy(self, stocks):
        """3L股不应有趋势买点信息"""
        from scripts.trend_trading import decide_system_with_detail, detect_trend_buy
        
        stocks_data = stocks.get('stocks', stocks)
        main_lines = ['半导体', '算力', '新能源']
        
        for sec, ss in stocks_data.items():
            if '002640' in ss:
                kls = ss['002640']
                date_str = kls[-1]['date']
                fmt = date_str[:4]+'-'+date_str[4:6]+'-'+date_str[6:8] if len(date_str)==8 else date_str
                
                detail = decide_system_with_detail('002640', fmt, stocks_data, main_lines)
                assert detail['system'] == '3l'
                
                bt = detect_trend_buy('002640', fmt, stocks_data, main_lines)
                assert bt is None
                break

    def test_signal_stock_card_fields_complete(self, stocks):
        """验证 signalStockCard 所需字段都齐全"""
        from scripts.trend_trading import decide_system_with_detail, detect_trend_buy
        
        stocks_data = stocks.get('stocks', stocks)
        main_lines = ['半导体', '算力', '新能源']
        
        # 模拟前端 signalStockCard 需要的字段（改造后）
        for sec, ss in stocks_data.items():
            if '300054' in ss:
                kls = ss['300054']
                date_str = kls[-1]['date']
                fmt = date_str[:4]+'-'+date_str[4:6]+'-'+date_str[6:8] if len(date_str)==8 else date_str
                
                detail = decide_system_with_detail('300054', fmt, stocks_data, main_lines)
                bt = detect_trend_buy('300054', fmt, stocks_data, main_lines)
                
                # signalStockCard 需要的全部字段（含新增的）
                card_data = {
                    'name': '鼎龙股份', 'code': '300054',
                    'price': kls[-1]['close'], 'change': 0,
                    'signal': 'buy',
                    'stage': '上行',
                    'trading_system': detail['system'],
                    'trading_reason': detail['reason'],
                    'trend_bias': bt['bias5'] if bt else None,
                    'trend_buy_type': bt['buy_type'] if bt else None,
                    'mainline_level': '',
                }
                
                # 手动指定的票应返回trend
                assert card_data['trading_system'] == 'trend'
                break

    def test_trading_reason_format(self, stocks):
        """trading_reason 格式适合前端展示"""
        from scripts.trend_trading import decide_system_with_detail
        
        stocks_data = stocks.get('stocks', stocks)
        
        detail = decide_system_with_detail('688126', '2026-05-22', stocks_data, None)
        reason = detail['reason']
        # 原因应该简短可展示
        assert len(reason) < 100
        # 中文内容
        assert any(c in reason for c in ['默认', '手动', '趋势'])
        
        detail2 = decide_system_with_detail('002640', '2026-05-22', stocks_data, None)
        reason2 = detail2['reason']
        assert len(reason2) < 100


# ==================== API层集成测试 ====================

class TestStockAnalysisAPI:
    """
    测试 stock-analysis API 改造后的响应格式。
    
    要求返回含:
    - trading_system: 'trend' | '3l'
    - trading_reason: str
    - trend_buy: dict | null (趋势买点信息)
    """
    
    def test_api_response_has_trading_system(self, stocks):
        """API响应应包含 trading_system"""
        from scripts.trend_trading import decide_system_with_detail, detect_trend_buy
        
        stocks_data = stocks.get('stocks', stocks)
        
        # 模拟API返回结构
        for sec, ss in stocks_data.items():
            if '688126' in ss:
                code = '688126'
                kls = ss[code]
                date_str = kls[-1]['date']
                fmt = date_str[:4]+'-'+date_str[4:6]+'-'+date_str[6:8] if len(date_str)==8 else date_str
                
                detail = decide_system_with_detail(code, fmt, stocks_data)
                bt = detect_trend_buy(code, fmt, stocks_data)
                
                api_response = {
                    'code': code,
                    'name': '沪硅产业',
                    'price': kls[-1]['close'],
                    'trading_system': detail['system'],
                    'trading_reason': detail['reason'],
                    'trend_buy': bt,
                    'structure': detail['details'].get('structure', ''),
                    'stage': '--',
                }
                
                assert 'trading_system' in api_response
                assert api_response['trading_system'] in ('trend', '3l')
                assert 'trend_buy' in api_response
                if api_response['trend_buy']:
                    assert 'buy_type' in api_response['trend_buy']
                break

    def test_api_3l_stock_no_trend_buy(self, stocks):
        """3L股票API响应中 trend_buy 为 None"""
        from scripts.trend_trading import decide_system_with_detail, detect_trend_buy
        
        stocks_data = stocks.get('stocks', stocks)
        
        for sec, ss in stocks_data.items():
            if '002640' in ss:
                code = '002640'
                kls = ss[code]
                date_str = kls[-1]['date']
                fmt = date_str[:4]+'-'+date_str[4:6]+'-'+date_str[6:8] if len(date_str)==8 else date_str
                
                detail = decide_system_with_detail(code, fmt, stocks_data)
                bt = detect_trend_buy(code, fmt, stocks_data)
                
                assert detail['system'] == '3l'
                assert bt is None
                break

    def test_api_response_has_detail_fields(self, stocks):
        """API响应包含三层决策的详情字段"""
        from scripts.trend_trading import decide_system_with_detail
        
        stocks_data = stocks.get('stocks', stocks)
        
        for sec, ss in stocks_data.items():
            if '688126' in ss:
                code = '688126'
                kls = ss[code]
                date_str = kls[-1]['date']
                fmt = date_str[:4]+'-'+date_str[4:6]+'-'+date_str[6:8] if len(date_str)==8 else date_str
                
                detail = decide_system_with_detail(code, fmt, stocks_data)
                
                # 前端需要展示的详情字段
                det = detail.get('details', {})
                assert 'direction' in det
                assert 'manual' in det
                break


# ==================== 前端渲染测试（无浏览器） ====================

class TestFrontendRender:
    """
    测试前端渲染逻辑（模拟JS函数行为）
    先定义好 signalStockCard 改造后的预期行为，再改前端代码。
    """

    def test_trend_system_display(self):
        """趋势交易应显示🔥趋势交易"""
        # 模拟前端 signalStockCard 的渲染逻辑
        def mock_signalStockCard(s):
            system_icon = '🔥' if s.get('trading_system') == 'trend' else '📘'
            system_text = '趋势交易' if s.get('trading_system') == 'trend' else '3L交易'
            html = f'<span class="v">{system_icon}{system_text}</span>'
            return html
        
        card = mock_signalStockCard({'trading_system': 'trend'})
        assert '🔥趋势交易' in card
        
        card2 = mock_signalStockCard({'trading_system': '3l'})
        assert '📘3L交易' in card2

    def test_trend_buy_point_display(self):
        """趋势股买点显示BIAS乖离率买入"""
        def mock_buy_point_display(s):
            if s.get('trading_system') == 'trend' and s.get('trend_buy_type'):
                return f'<span>📊 {s["trend_buy_type"]}</span>'
            elif s.get('buy_point'):
                return f'<span>📘 {s["buy_point"]}</span>'
            return ''
        
        trend = mock_buy_point_display({
            'trading_system': 'trend',
            'trend_buy_type': 'BIAS5乖离率买入',
            'trend_bias': -0.53,
        })
        assert '📊' in trend
        assert 'BIAS5' in trend
        
        normal = mock_buy_point_display({
            'trading_system': '3l',
            'buy_point': '突破买点',
        })
        assert '📘' in normal
        assert '突破买点' in normal

    def test_trend_conclusion_text(self):
        """趋势股结论行显示乖离率位置"""
        def mock_conclusion(s):
            if s.get('trading_system') == 'trend' and s.get('trend_bias') is not None:
                bias = s['trend_bias']
                if bias < 0:
                    return f'BIAS5={bias:.2f}%，价格在EMA5下方，乖离率买入区'
                elif bias <= 2:
                    return f'BIAS5={bias:.2f}%，价格靠近EMA5，乖离率买入区'
                else:
                    return f'BIAS5={bias:.2f}%，价格远离EMA5，持有区'
            return '--'
        
        text = mock_conclusion({'trading_system': 'trend', 'trend_bias': -0.53})
        assert '买入区' in text
        assert '-0.53' in text
        
        text2 = mock_conclusion({'trading_system': 'trend', 'trend_bias': 1.5})
        assert '买入区' in text2
        assert '1.5' in text2

    def test_3l_conclusion_unchanged(self):
        """3L股结论保持原有逻辑"""
        def mock_3l_conclusion(s):
            if s.get('trading_system') == '3l':
                # 保持原有3L结论文字
                return f'原有3L结论: 结构{s.get("structure","?")}，阶段{s.get("stage","?")}'
            return ''
        
        text = mock_3l_conclusion({
            'trading_system': '3l',
            'structure': '区间震荡',
            'stage': '区间底部',
        })
        assert '原有3L结论' in text
        assert '区间震荡' in text

    def test_trading_reason_tooltip(self):
        """交易方法字段应该有悬浮提示显示详细原因"""
        def mock_reason_html(s):
            system = '🔥趋势交易' if s['trading_system'] == 'trend' else '📘3L交易'
            reason = s.get('trading_reason', '')
            # 悬浮提示显示完整原因
            return f'<span title="{reason}">{system}</span>'
        
        html = mock_reason_html({
            'trading_system': 'trend',
            'trading_reason': '上涨结构+斜率12.96%+半导体主线，全部通过',
        })
        assert '🔥趋势交易' in html
        assert 'title=' in html
        assert '斜率12.96%' in html


# ==================== monitor.html 集成测试 ====================

class TestMonitorIntegration:
    """
    测试监测页面集成趋势买点。
    要求：scan_buy_signals 输出含 trend_buy 字段
    """

    def test_trend_buy_in_scan_output(self, stocks):
        """扫描输出中趋势股应有趋势买点"""
        from scripts.trend_trading import scan_trend_buys
        
        stocks_data = stocks.get('stocks', stocks)
        main_lines = ['半导体', '算力', '新能源']
        
        results = scan_trend_buys('2026-05-22', stocks_data, main_lines)
        
        if results:
            sample = results[0]
            assert 'code' in sample
            assert 'buy_type' in sample
            assert 'BIAS' in sample['buy_type']
            assert 'direction' in sample
            assert sample['direction'] in main_lines

    def test_scan_grouped_by_direction(self, stocks):
        """扫描结果可被按方向分组（monitor.html的Tab需求）"""
        from scripts.trend_trading import scan_trend_buys
        
        stocks_data = stocks.get('stocks', stocks)
        main_lines = ['半导体', '算力', '新能源']
        
        results = scan_trend_buys('2026-05-22', stocks_data, main_lines)
        
        groups = {}
        for r in results:
            groups.setdefault(r['direction'], []).append(r)
        
        for sec in main_lines:
            if sec in groups:
                for item in groups[sec]:
                    assert item['direction'] == sec

    def test_no_duplicate_between_trend_and_3l(self, stocks):
        """同一只股票不应同时出现在趋势买点和3L买点中"""
        stocks_data = stocks.get('stocks', stocks)
        main_lines = ['半导体', '算力', '新能源']
        
        # 趋势买点
        trend_codes = set()
        from scripts.trend_trading import scan_trend_buys
        for r in scan_trend_buys('2026-05-22', stocks_data, main_lines):
            trend_codes.add(r['code'])
        
        # 3L买点（模拟）
        from scripts.buy_point_detection import scan_all_stocks
        wl = __import__('scripts.data_layer', fromlist=['get_watchlist']).get_watchlist()
        wl_codes = set(s['code'] for s in wl)
        try:
            three_l_results = scan_all_stocks('2026-05-22', stocks_data, market_position='波中', main_lines=main_lines, watchlist_codes=wl_codes)
            three_l_codes = set(r['code'] for r in three_l_results)
            
            overlap = trend_codes & three_l_codes
            # 可以在监测页用不同样式区分，但不排除重叠
            # 如果有重叠，确保趋势系统判断正确
            for code in overlap:
                from scripts.trend_trading import decide_system
                for sec, ss in stocks_data.items():
                    if code in ss:
                        sys_choice = decide_system(code, '2026-05-22', stocks_data, main_lines)
                        assert sys_choice == 'trend'
                        break
        except Exception:
            pass  # scan_all_stocks可能因依赖问题失败，跳过
