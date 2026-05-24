"""
构建同花顺板块/概念名称缓存
输出: data/3l/board_names_cache.json
"""
import os, json
os.environ['TQDM_DISABLE'] = '1'
import akshare as ak

DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')
OUTPUT = os.path.join(DATA_DIR, 'board_names_cache.json')

# 行业板块
ind_df = ak.stock_board_industry_name_ths()
industry_names = [{'name': r['name'], 'code': str(r['code']), 'type': 'industry'} for _, r in ind_df.iterrows()]

# 概念板块
con_df = ak.stock_board_concept_name_ths()
concept_names = [{'name': r['name'], 'code': str(r['code']), 'type': 'concept'} for _, r in con_df.iterrows()]

data = {
    'industry': ind_df['name'].tolist(),
    'concept': con_df['name'].tolist(),
    'all': industry_names + concept_names,
}

with open(OUTPUT, 'w') as f:
    json.dump(data, f, ensure_ascii=False)

print(f'行业板块: {len(industry_names)}个')
print(f'概念板块: {len(concept_names)}个')
print(f'总计: {len(data["all"])}个')
print(f'保存到: {OUTPUT}')
