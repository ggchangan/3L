"""
资料投喂服务 — 链接抓取、PDF解析、LLM摘要和打标签
"""
import json
import os
import re
import sys
import hashlib
from datetime import datetime
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_store():
    from backend.core.logic_tracking_store import LogicTrackingStore
    return LogicTrackingStore()


# ═══════════════════════════════════════════════════
# URL 内容提取
# ═══════════════════════════════════════════════════

def extract_url_content(url):
    """从URL提取文章标题和正文摘要

    Returns: {'title': str, 'text': str, 'source_name': str} or {'error': str}
    """
    try:
        import requests
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        r = requests.get(url, headers=headers, timeout=15)
        r.encoding = 'utf-8'
        html = r.text
    except Exception as e:
        return {'error': f'抓取失败: {e}'}

    # 提取标题
    title = ''
    title_m = re.search(r'<title>(.*?)</title>', html, re.DOTALL)
    if title_m:
        title = title_m.group(1).strip()
    # 微信文章专用标题
    og_title = re.search(r'<meta[^>]*property="og:title"[^>]*content="([^"]*)"', html)
    if og_title:
        title = og_title.group(1)

    # 提取正文
    text = ''
    # 优先微信文章
    js_content = re.search(r'id="js_content"[^>]*>(.*?)</div>\s*<script', html, re.DOTALL)
    if js_content:
        text = re.sub(r'<[^>]+>', '', js_content.group(1))
        text = re.sub(r'\s+', ' ', text).strip()
    else:
        # 通用：去掉脚本和样式后取body
        body = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
        if body:
            cleaned = re.sub(r'<script[^>]*>.*?</script>', '', body.group(1), flags=re.DOTALL)
            cleaned = re.sub(r'<style[^>]*>.*?</style>', '', cleaned, flags=re.DOTALL)
            text = re.sub(r'<[^>]+>', '', cleaned)
            text = re.sub(r'\s+', ' ', text).strip()

    # 截取前2000字做摘要
    summary = text[:2000] if text else ''

    # 提取来源名
    domain = urlparse(url).netloc
    source_map = {
        'mp.weixin.qq.com': '微信公众号',
        'xueqiu.com': '雪球',
        '36kr.com': '36氪',
        'cls.cn': '财联社',
    }
    source_name = source_map.get(domain, domain)

    return {
        'title': title or f'文章({domain})',
        'text': summary,
        'source_name': source_name,
        'url': url,
    }


# ═══════════════════════════════════════════════════
# LLM 处理
# ═══════════════════════════════════════════════════

def _call_llm(prompt, max_tokens=1024):
    """调用LLM API

    环境变量 LLM_API_KEY 和 LLM_API_URL 可配置。
    默认用 DeepSeek 兼容格式。
    """
    api_key = os.environ.get('LLM_API_KEY', '')
    api_url = os.environ.get('LLM_API_URL', 'https://api.deepseek.com/v1/chat/completions')

    if not api_key:
        return None

    try:
        import requests
        resp = requests.post(api_url, json={
            'model': os.environ.get('LLM_MODEL', 'deepseek-chat'),
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': max_tokens,
            'temperature': 0.3,
        }, headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }, timeout=30)
        data = resp.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return None


def llm_summarize(text, title=''):
    """LLM生成摘要

    Returns: str or None (LLM不可用时返回None)
    """
    prompt = f"""请为以下文章生成一个简短的摘要（100字以内），突出核心观点：

标题：{title[:200]}
内容：{text[:1500]}

摘要："""
    return _call_llm(prompt)


def llm_extract_core_logic(text, title, existing_tags):
    """LLM提取核心逻辑（独立于摘要）

    Returns: str or None (LLM不可用时返回None)
    """
    tags_desc = '\n'.join([
        f"- {t['name']} (行业: {','.join(t.get('related_industries', []))})"
        for t in existing_tags[:5]
    ]) if existing_tags else '暂无已有逻辑标签'

    prompt = f"""以下是一篇与股市投资相关的文章，请提取它的「核心逻辑」——即文章最核心的投资逻辑、驱动因素或主线观点。

格式要求：
- 用1-2句话概括核心逻辑
- 指出驱动的行业/板块
- **列出文中提到的所有受益公司及A股代码**（包括龙头标的、产业链相关公司、可能受益的方向。即使只是行业泛指，也尽量列出合理的对标公司）

要求：**尽量全面地提取所有相关公司，不要遗漏。**

标题：{title[:200]}
内容：{text[:2000]}

已有逻辑标签参考：
{tags_desc}

核心逻辑："""
    return _call_llm(prompt, max_tokens=512)


def llm_suggest_new_tags(text, title):
    """LLM从文章提取候选新逻辑标签（当无已有标签时）

    Returns: [{id, name, description, industries, related_stocks}, ...] or None
    """
    prompt = f"""以下是一篇与股市投资相关的文章。请从文章中提取可能的「投资逻辑」——即事件驱动→影响的逻辑链。

每个逻辑应遵循「事件 → 驱动方向 → 受益环节」的格式。

返回JSON数组，每项包含：
- id: 简短英文ID（如 tag-huawei-advanced-pkg）
- name: 逻辑名称（事件+驱动方向，如"华为τ定律→先进封装升级"）
- description: 展开说明逻辑链条和影响
- industries: 关联行业数组
- related_stocks: 个股列表，每项为 {{"code": "600584", "name": "长电科技"}} 格式。提取文章中提到或合理推断的受益A股，**尽量提取所有相关个股并补上中文名称**；未找到则填[]

要求：
- 提取2-4个最核心的逻辑
- 逻辑名称要有因果关系，不要只是行业名称
- **尽量提取所有相关的个股**，包括文中直接提到的和产业链中与之关联的龙头公司，**必须同时附上股票代码和中文名称**
- 只返回JSON数组，不要其他文字

文章标题：{title[:200]}
文章内容：{text[:2000]}

JSON："""

    result = _call_llm(prompt, max_tokens=1024)
    if not result:
        return None

    try:
        parsed = json.loads(result)
        if isinstance(parsed, list):
            return parsed
        return None
    except json.JSONDecodeError:
        arr_match = re.search(r'\[.*?\]', result, re.DOTALL)
        if arr_match:
            try:
                return json.loads(arr_match.group())
            except json.JSONDecodeError:
                pass
        return None


def llm_suggest_tags(text, title, existing_tags):
    """LLM推荐匹配的逻辑标签

    Args:
        text: 文章正文
        title: 文章标题
        existing_tags: [{id, name, related_industries}, ...]

    Returns: [{tag_id, tag_name, confidence, reason}, ...] or None
    """
    if not existing_tags:
        return []

    tags_desc = '\n'.join([
        f"- {t['id']}: {t['name']} (行业: {','.join(t.get('related_industries', []))})"
        for t in existing_tags
    ])

    prompt = f"""我有以下逻辑标签：
{tags_desc}

新文章标题：{title[:200]}
文章内容摘要：{text[:1000]}

请判断这篇文章匹配哪些逻辑标签。返回JSON数组，每项包含 tag_id, tag_name, confidence(0-100整数), reason。
如果不匹配任何标签，返回空数组[]。
只返回JSON，不要其他文字："""

    result = _call_llm(prompt)
    if not result:
        return None

    try:
        # 尝试解析JSON
        parsed = json.loads(result)
        if isinstance(parsed, list):
            return parsed
        return None
    except json.JSONDecodeError:
        # 尝试提取JSON数组
        arr_match = re.search(r'\[.*?\]', result, re.DOTALL)
        if arr_match:
            try:
                return json.loads(arr_match.group())
            except json.JSONDecodeError:
                pass
        return None


# ═══════════════════════════════════════════════════
# 方案C打标签（关键词+LLM混合）
# ═══════════════════════════════════════════════════

def match_tags(text, title, existing_tags):
    """方案C：关键词粗筛+LLM语义匹配

    先用关键词匹配推荐标签，低置信度或无结果时走LLM。
    返回：推荐标签列表 + 是否使用了LLM
    """
    from backend.services.logic_matcher import LogicMatcher
    matcher = LogicMatcher(existing_tags)

    # 先用关键词匹配
    keyword_results = matcher.keyword_match('', title, '')
    # 也在正文中搜行业关键词
    for tag in existing_tags:
        for ind in tag.get('related_industries', []):
            if ind and len(ind) >= 2 and text and ind in text:
                keyword_results.append({
                    'tag_id': tag['id'],
                    'tag_name': tag.get('name', ''),
                    'confidence': 40,
                    'reason': f'内容行业匹配({ind})',
                })

    # 去重（保留置信度高的）
    seen = {}
    for r in keyword_results:
        tid = r['tag_id']
        if tid not in seen or r['confidence'] > seen[tid]['confidence']:
            seen[tid] = r
    keyword_results = sorted(seen.values(), key=lambda r: r['confidence'], reverse=True)

    # 关键词匹配有高置信度结果 → 直接返回
    high_confidence = [r for r in keyword_results if r['confidence'] >= 50]
    if high_confidence:
        return {'tags': high_confidence, 'llm_used': False}

    # 低置信度或无结果 → 走LLM
    llm_results = llm_suggest_tags(text, title, existing_tags)
    if llm_results:
        return {'tags': llm_results, 'llm_used': True}

    # LLM不可用 → 返回关键词结果
    return {'tags': keyword_results, 'llm_used': False}


# ═══════════════════════════════════════════════════
# 投喂处理
# ═══════════════════════════════════════════════════

def process_feed(url, source_type='wechat', source_subtype=''):
    """处理URL投喂：抓取→提取→打标签→提取核心逻辑→返回预览

    Args:
        url: 文章链接
        source_type: 'wechat' | 'report' | 'douyin'
        source_subtype: 公众号子类型 'industry' | 'review' | 'other'

    Returns: 预览数据，包含提取结果+推荐标签+核心逻辑
    """
    # 1. 提取内容
    content = extract_url_content(url)
    if 'error' in content:
        return content

    store = _get_store()
    tags = store.get_tags()

    # 2. 尝试LLM摘要
    summary = content['text'][:500]  # 保底摘录
    llm_summary = llm_summarize(content['text'], content['title'])
    if llm_summary:
        summary = llm_summary

    # 3. 打标签
    tag_result = match_tags(content['text'], content['title'], tags)

    # 4. 提取核心逻辑
    core_logic = llm_extract_core_logic(content['text'], content['title'], tags)

    # 5. 如果无已有标签或匹配结果为空，尝试从文章提取候选新标签
    suggested_new_tags = []
    if not tags or not tag_result['tags']:
        new_tags = llm_suggest_new_tags(content['text'], content['title'])
        if new_tags:
            suggested_new_tags = new_tags

    return {
        'title': content['title'],
        'summary': summary,
        'core_logic': core_logic or '',
        'source_name': content['source_name'],
        'source_type': source_type,
        'source_subtype': source_subtype,
        'url': content['url'],
        'recommended_tags': tag_result['tags'],
        'suggested_new_tags': suggested_new_tags,
        'llm_used': tag_result['llm_used'],
    }


def save_feed(data):
    """保存投喂条目

    Args:
        data: {
            title, summary, core_logic, source_name, source_type, source_subtype, url,
            logic_tags: [tag_id, ...],
            industries: [str, ...],
            companies: [code, ...],
        }

    Returns: {'success': True} or {'error': str}
    """
    store = _get_store()
    url = data.get('url', '')
    if url:
        # 去重：检查相同URL是否已存在
        existing = store.get_entries()
        for e in existing:
            if e.get('url') == url:
                return {'success': False, 'error': '该链接已投喂过了', 'duplicate': True}
    entry_id = 'feed-' + hashlib.md5(url.encode()).hexdigest()[:12]

    entry = {
        'id': entry_id,
        'source_type': data.get('source_type', 'link'),
        'source_subtype': data.get('source_subtype', ''),
        'source_name': data.get('source_name', ''),
        'title': data.get('title', ''),
        'summary': data.get('summary', ''),
        'core_logic': data.get('core_logic', ''),
        'url': data.get('url', ''),
        'industries': data.get('industries', []),
        'companies': data.get('companies', []),
        'extracted_logics': data.get('extracted_logics', []),
        'logic_tags': data.get('logic_tags', []),
        'fed_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'verify': {
            '3d_return': 0.0, '5d_return': 0.0, '10d_return': 0.0,
            'sector_rank_before': None, 'sector_rank_after': None,
            'buy_signal_count': 0, 'summary': '',
            'score': None, 'verified_at': None,
        },
    }
    store.add_entry(entry)
    return {'success': True, 'entry': entry}
