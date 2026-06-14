"""
外围美股异动分析服务
- 搜索美股相关新闻
- 返回原因摘要
"""
import json
import os
import re
import requests

from backend.core.config import DATA_DIR

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _search_us_stock_news(code):
    """搜索指定美股的近期新闻"""
    try:
        # 使用东财个股新闻API（JSONP格式），用美股代码搜索
        cb = "jQuery_news"
        inner_params = json.dumps({
            "uid": "",
            "keyword": code,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {"cmsArticleWebOld": {
                "searchScope": "default", "sort": "default",
                "pageIndex": 1, "pageSize": 10,
                "preTag": "", "postTag": "",
            }},
        }, separators=(',', ':'))
        url = "https://search-api-web.eastmoney.com/search/jsonp"
        params = {"cb": cb, "param": inner_params}
        headers = {
            "User-Agent": UA,
            "Referer": "https://so.eastmoney.com/",
        }
        r = requests.get(url, params=params, headers=headers, timeout=10)
        text = r.text
        # 解析 JSONP
        json_str = text[text.index("(") + 1: text.rindex(")")]
        d = json.loads(json_str)
        articles = d.get("result", {}).get("cmsArticleWebOld", []) or []
        results = []
        for a in articles:
            results.append({
                "title": re.sub(r'<[^>]+>', '', a.get("title", "")),
                "time": a.get("date", ""),
                "source": a.get("mediaName", ""),
                "url": a.get("url", ""),
            })
        return results
    except Exception:
        return []


def analyze_us_stock_abnormal(code, name, change_pct):
    """分析美股异动原因"""
    if not code:
        return {"success": False, "error": "股票代码不能为空"}

    news = _search_us_stock_news(code)

    # 生成摘要
    if news:
        top_titles = "；".join(n["title"] for n in news[:3])
        summary = f"「{name}」今日涨跌幅 {change_pct:+.2f}%。相关新闻报道：{top_titles}"
    else:
        summary = f"「{name}」今日涨跌幅 {change_pct:+.2f}%。暂无相关新闻，可能受大盘或板块整体走势影响。"

    # 查询映射表获取A股影响
    related_a_shares = _find_related_a_shares(code)

    return {
        "success": True,
        "code": code,
        "name": name,
        "change_pct": change_pct,
        "news": news,
        "summary": summary,
        "related_a_shares": related_a_shares,
    }


def _find_related_a_shares(code):
    """从映射表查找关联A股"""
    try:
        ext_path = os.path.join(
            DATA_DIR,
            'public', 'external_mapping.json'
        )
        if not os.path.isfile(ext_path):
            return []
        with open(ext_path, encoding='utf-8') as f:
            data = json.load(f)
        related = []
        for cat in data.get('categories', []):
            for s in cat.get('stocks', []):
                if s.get('code', '').upper() == code.upper():
                    # 从 impact 解析A股板块
                    impact = s.get('impact', '')
                    if impact:
                        related.append(impact)
        return list(set(related))
    except Exception:
        return []
