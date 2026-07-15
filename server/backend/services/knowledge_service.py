"""
知识库服务 — 知识库/交易技巧/日志
"""
import json, os, re, tempfile, zipfile, shutil
from datetime import datetime
from backend.core.config import KB_BASE, TRADING_TIPS_DIR, PRIVATE_DIR, WWW_DIR, DATA_DIR


def get_kb_files():
    """
    列出知识库下所有 .md / .pdf 文件的相对路径。
    Returns: list of relative paths (sorted)
    """
    files = []
    for root, dirs, fnames in os.walk(KB_BASE):
        for fn in fnames:
            if fn.endswith('.md') or fn.endswith('.pdf'):
                rel_path = os.path.relpath(os.path.join(root, fn), KB_BASE)
                files.append(rel_path)
    files.sort()
    return files


def download_kb_all():
    """
    将知识库所有 .md / .pdf 文件打包为 zip，返回 zip 文件路径。
    调用方需负责使用完毕后清理临时文件。
    Returns: str — zip 文件路径
    """
    zip_path = os.path.join(tempfile.gettempdir(), '3L_knowledge_base.zip')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, fnames in os.walk(KB_BASE):
            for fn in fnames:
                if fn.endswith('.md') or fn.endswith('.pdf'):
                    fp = os.path.join(root, fn)
                    rel = os.path.relpath(fp, KB_BASE)
                    zf.write(fp, rel)
    return zip_path


def download_kb_file(rel):
    """知识库文件下载（路径安全校验 + 文件读取）"""
    import urllib.parse
    rel = urllib.parse.unquote(rel)
    rel_path = os.path.normpath(rel)
    if rel_path.startswith('..') or rel_path.startswith('/'):
        return None, 'forbidden'
    fp = os.path.join(KB_BASE, rel_path)
    if not os.path.isfile(fp):
        return None, 'not found'
    return fp, None


def get_tips_list():
    """
    读取交易技巧目录（TRADING_TIPS_DIR）下的所有 .md 文件，
    提取标题 / 描述 / 收录日期。
    Returns: dict {'tips': [...]}
    """
    tips = []
    if os.path.isdir(TRADING_TIPS_DIR):
        for f in sorted(os.listdir(TRADING_TIPS_DIR)):
            if not f.endswith('.md'):
                continue
            fp = os.path.join(TRADING_TIPS_DIR, f)
            title = f.replace('.md', '')
            desc = ''
            date_added = ''
            try:
                with open(fp, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                    title_m = re.search(r'^# (.+)$', content, re.MULTILINE)
                    if title_m:
                        title = title_m.group(1)
                    desc_m = re.search(r'^> (.+)$', content, re.MULTILINE)
                    if desc_m:
                        desc = desc_m.group(1)
                    if not desc:
                        clean = re.sub(r'[#>\-*\n\r]', '', content)[:150].strip()
                        desc = clean[:120] + '...' if len(clean) > 120 else clean
                    date_m = re.search(r'收录日期[：:]\s*(\d{4}-\d{2}-\d{2})', content)
                    if date_m:
                        date_added = date_m.group(1)
            except Exception:
                pass
            tips.append({
                'id': f.replace('.md', ''),
                'title': title,
                'desc': desc,
                'file': f,
                'is_journal': f == '交易日志的重要性.md',
                'date_added': date_added,
            })
    return {'tips': tips}


def get_journal_entries():
    """
    读取交易日志条目。
    Returns: dict {'entries': [...]}
    """
    jf = os.path.join(PRIVATE_DIR, 'journal_entries.json')
    if os.path.isfile(jf):
        with open(jf, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'entries': []}


def get_tip_content(file_name):
    """
    读取指定交易技巧 .md 文件的内容。
    Args:
        file_name: 文件名（如 '交易系统原则.md'）
    Returns: dict {'title': str, 'content': str}
    """
    fp = os.path.join(TRADING_TIPS_DIR, file_name)
    if not os.path.isfile(fp):
        return {'error': 'file not found', 'title': '', 'content': ''}
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    return {'title': file_name.replace('.md', ''), 'content': content}


_kb_subdir_map = {'tips': 'trading_tips', 'industry': 'industry_tracking'}
_industry_cat_order = ['公司', '行业', '研报', '逻辑']


def get_kb_list(kb_type):
    """
    获取知识库列表。
    Args:
        kb_type: 'tips'（平铺）或 'industry'（按子目录：公司/行业/研报/逻辑）
    Returns: dict {'items': [...]}
    """
    subdir = _kb_subdir_map.get(kb_type, '')
    if not subdir:
        return {'items': [], 'error': 'invalid type'}
    kb_dir = os.path.join(KB_BASE, subdir)
    items = []
    if not os.path.isdir(kb_dir):
        return {'items': items}

    if kb_type == 'tips':
        # flat: read .md files directly
        for f in sorted(os.listdir(kb_dir)):
            if not f.endswith('.md'):
                continue
            fp = os.path.join(kb_dir, f)
            title = f.replace('.md', '')
            desc = ''
            date_added = ''
            try:
                with open(fp, 'r', encoding='utf-8') as fh:
                    content = fh.read()
                    title_m = re.search(r'^# (.+)$', content, re.MULTILINE)
                    if title_m:
                        title = title_m.group(1)
                    desc_m = re.search(r'^> (.+)$', content, re.MULTILINE)
                    if desc_m:
                        desc = desc_m.group(1)
                    if not desc:
                        clean = re.sub(r'[#>\-*\n\r]', '', content)[:150].strip()
                        desc = clean[:120] + '...' if len(clean) > 120 else clean
                    date_m = re.search(r'收录日期[：:]\s*(\d{4}-\d{2}-\d{2})', content)
                    if date_m:
                        date_added = date_m.group(1)
            except Exception:
                pass
            items.append({
                'id': f.replace('.md', ''),
                'title': title,
                'desc': desc,
                'file': f,
                'category': 'tips',
                'date_added': date_added,
            })
    else:
        # industry: read subdirectories (公司/行业/研报/逻辑)
        for cat in _industry_cat_order:
            cat_dir = os.path.join(kb_dir, cat)
            if not os.path.isdir(cat_dir):
                continue
            for f in sorted(os.listdir(cat_dir)):
                if not f.endswith('.md'):
                    continue
                fp = os.path.join(cat_dir, f)
                title = f.replace('.md', '')
                desc = ''
                date_added = ''
                try:
                    with open(fp, 'r', encoding='utf-8') as fh:
                        content = fh.read()
                        title_m = re.search(r'^# (.+)$', content, re.MULTILINE)
                        if title_m:
                            title = title_m.group(1)
                        desc_m = re.search(r'^> (.+)$', content, re.MULTILINE)
                        if desc_m:
                            desc = desc_m.group(1)
                        if not desc:
                            clean = re.sub(r'[#>\-*\n\r]', '', content)[:150].strip()
                            desc = clean[:120] + '...' if len(clean) > 120 else clean
                        date_m = re.search(r'收录日期[：:]\s*(\d{4}-\d{2}-\d{2})', content)
                        if date_m:
                            date_added = date_m.group(1)
                except Exception:
                    pass
                items.append({
                    'id': f.replace('.md', ''),
                    'title': title,
                    'desc': desc,
                    'file': f'{cat}/{f}',
                    'category': cat,
                    'date_added': date_added,
                })
    return {'items': items}


def get_kb_content(file_name, kb_type='tips'):
    """
    读取知识库文件内容。
    Args:
        file_name: 文件名（如 '交易系统原则.md'，industry 类型含子目录前缀如 '公司/xxx.md'）
        kb_type: 'tips' 或 'industry'
    Returns: dict {'title': str, 'content': str}
    """
    subdir = _kb_subdir_map.get(kb_type, 'trading_tips')
    fp = os.path.join(KB_BASE, subdir, file_name)
    if not os.path.isfile(fp):
        return {'error': 'file not found', 'title': '', 'content': ''}
    with open(fp, 'r', encoding='utf-8') as f:
        content = f.read()
    return {'title': file_name.replace('.md', ''), 'content': content}


def save_journal_entry(entry):
    """
    追加一条交易日志条目到 journal_entries.json。
    Args:
        entry: dict，至少包含 date / content 等字段
    Returns: dict {'status': str, 'id': str}
    """
    jf = os.path.join(PRIVATE_DIR, 'journal_entries.json')
    entries_data = {'entries': []}
    if os.path.isfile(jf):
        with open(jf, 'r', encoding='utf-8') as f:
            entries_data = json.load(f)

    entry_id = entry.get('date', datetime.now().strftime('%Y%m%d')) + '_' + str(len(entries_data['entries']))
    entry['id'] = entry_id
    entry['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entries_data['entries'].insert(0, entry)

    os.makedirs(os.path.dirname(jf), exist_ok=True)
    with open(jf, 'w', encoding='utf-8') as f:
        config.atomic_json_dump(entries_data, f.name, indent=2)

    return {'status': 'ok', 'id': entry_id}
