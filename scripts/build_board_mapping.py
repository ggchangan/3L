"""
构建 同花顺行业板块 → 成分股 映射文件
输出: data/3l/board_constituents.json
      {board_name: [{code, name, industry}, ...], ...}
"""
import os, json, time, requests, re
os.environ['TQDM_DISABLE'] = '1'
import akshare as ak

DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')
OUTPUT_PATH = os.path.join(DATA_DIR, 'board_constituents.json')

def get_all_th_boards():
    """获取所有同花顺行业板块名称和代码"""
    df = ak.stock_board_industry_name_ths()
    return df.to_dict('records')  # [{name, code}, ...]

def get_industry_map():
    """加载现有行业映射"""
    path = os.path.join(DATA_DIR, 'stock_industry_map.json')
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)
    return {}

def get_stock_names():
    """从 all_stocks_60d.json 加载股票名称"""
    sp = os.path.join(DATA_DIR, 'all_stocks_60d.json')
    if os.path.isfile(sp):
        with open(sp) as f:
            data = json.load(f)
        names = {}
        stocks = data.get('stocks', data) if isinstance(data, dict) else data
        for sec, codes in (stocks.items() if isinstance(stocks, dict) else []):
            for code, kls in codes.items():
                if kls and isinstance(kls, list) and len(kls) > 0:
                    names[code] = kls[0].get('name', '')
        return names
    return {}

def build_mapping():
    boards = get_all_th_boards()
    industry_map = get_industry_map()
    stock_names = get_stock_names()
    
    # 先按 ths_industry 反向建立股票索引
    industry_to_stocks = {}
    for code, info in industry_map.items():
        ind = info.get('ths_industry', '')
        if ind:
            if ind not in industry_to_stocks:
                industry_to_stocks[ind] = []
            industry_to_stocks[ind].append({
                'code': code,
                'name': stock_names.get(code, ''),
                'industry': ind,
            })
    
    result = {}
    for board in boards:
        name = board['name']
        code = board['code']
        
        # 从 stock_industry_map 的 ths_industry 反向匹配
        stocks = industry_to_stocks.get(name, [])
        
        if stocks:
            result[name] = stocks
            # print(f'  {name}: {len(stocks)}只')
        else:
            result[name] = []
    
    # 保存
    with open(OUTPUT_PATH, 'w') as f:
        json.dump({'boards': result, 'count': len(result)}, f, ensure_ascii=False, indent=2)
    
    print(f'\n完成: {len(result)}个板块, 输出到 {OUTPUT_PATH}')

if __name__ == '__main__':
    build_mapping()
