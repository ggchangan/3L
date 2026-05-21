#!/usr/bin/env python3
"""
波峰波谷判定综合PDF — 标准方案：HTML→wkhtmltopdf
和"加速判定算法"PDF同一方式
"""
import subprocess, os, tempfile, shutil

OUTPUT = '/home/ubuntu/www/files/波峰波谷判定_综合文档.pdf'
CHART_PATH = '/home/ubuntu/www/files/bias_v5_multi_index.png'
WIDTH = '1200px'

def gen_html():
    return f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body {{ font-family: 'Noto Sans SC', 'SimSun', 'Microsoft YaHei', sans-serif; margin: 20px; padding: 0; }}
h1 {{ color: #d32f2f; font-size: 24px; border-bottom: 2px solid #d32f2f; padding-bottom: 5px; }}
h2 {{ color: #1976d2; font-size: 20px; margin-top: 30px; }}
h3 {{ color: #333; font-size: 16px; margin-top: 20px; }}
table {{ border-collapse: collapse; width: 100%; margin: 15px 0; font-size: 13px; }}
th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: center; }}
th {{ background-color: #f5f5f5; font-weight: bold; }}
tr:nth-child(even) {{ background-color: #fafafa; }}
.code {{ background: #f8f8f8; border: 1px solid #ddd; padding: 10px; margin: 10px 0; font-family: 'Consolas','Courier New',monospace; font-size: 12px; white-space: pre-wrap; }}
.note {{ background: #fff3e0; border-left: 4px solid #ff9800; padding: 8px 12px; margin: 10px 0; font-size: 13px; }}
img {{ max-width: 100%; margin: 10px 0; }}
</style></head><body>

<h1>大盘波峰波谷判定 V5 算法</h1>
<p style="color:#666;font-size:14px;">基于乖离率趋势转折的置信度评分方案 &nbsp;|&nbsp; 2026-05-22 上线</p>

<h2>一、算法概述</h2>
<p>V5方案从"跌了多少是波谷、涨了多少是波峰"的误区中走出来，转向检测"趋势是否在掉头"。</p>
<p><b>核心思路：</b>波峰的本质是趋势从上涨转向下跌的前期征兆，波谷的本质是趋势从下跌转向上涨的前期征兆。因此，与其用固定阈值判断"多高算高、多低算低"，不如判断做多动能是否耗尽（波峰）、做空动能是否耗尽（波谷）。</p>
<p>评分方法：4个独立条件各得0/1分，pk_score/vl_score分别0~4分。pk_score≥4或bias20>8%判偏波峰，vl_score≥4或bias20<-8%判偏波谷。pk_score≥3或vl_score≥3为波中偏上/偏下，其余为波中。</p>

<h2>二、评分条件</h2>
<h3>pk_score（波峰置信度，0~4分）</h3>
<ul>
<li><b>① 趋势转折：</b>过去10天bias上升>0.5% + 近5天平/降（先升后平/降，"冲不动"）</li>
<li><b>② 乖离率位置：</b>bias20 > +1.5%（处于偏高位置）</li>
<li><b>③ 量价信号：</b>放量滞涨/长上影/加速衰竭，任1触发</li>
<li><b>④ 趋势确认：</b>bias20 3日变化转负</li>
</ul>
<h3>vl_score（波谷置信度，0~4分）</h3>
<ul>
<li><b>① 趋势转折：</b>过去10天bias下降>0.8% + 近5天平/升</li>
<li><b>② 乖离率位置：</b>bias20 < -1.5%</li>
<li><b>③ 量价信号：</b>恐慌出清/锤子线/连续阴跌地量，任1触发</li>
<li><b>④ 趋势确认：</b>bias20 3日变化转正</li>
</ul>
<div class="note">极端值自动升级：bias20 > 8%时pk_score自动≥3，bias20 < -8%时vl_score自动≥3。</div>

<h2>三、5档判定映射</h2>
<table>
<tr><th>档位</th><th>条件</th><th>建仓%/只</th><th>目标仓位</th><th>策略</th></tr>
<tr><td>偏波峰</td><td>pk≥4或bias20>8%</td><td>5%/只</td><td>五成</td><td>控仓，卖出可不补</td></tr>
<tr><td>波中偏上</td><td>pk_score≥3</td><td>5%/只</td><td>六至七成</td><td>偏防守，收紧止盈</td></tr>
<tr><td>波中</td><td>pk<3且vl<3</td><td>5%/只</td><td>80%以上</td><td>正常交易积极选股</td></tr>
<tr><td>波中偏下</td><td>vl_score≥3</td><td>10%/只</td><td>五至七成</td><td>偏进攻，卖出当日补回</td></tr>
<tr><td>偏波谷</td><td>vl≥4或bias20<-8%</td><td>10%/只</td><td>80%~100%</td><td>积极寻找买点</td></tr>
</table>

<h2>四、量价信号详情（大盘版）</h2>
<h3>波峰信号</h3>
<table>
<tr><th>信号</th><th>英文名</th><th>规则</th></tr>
<tr><td>放量滞涨</td><td>churn</td><td>量>1.3×MA20 + 实体<0.8%</td></tr>
<tr><td>长上影回撤</td><td>rejection</td><td>上影>1.5% + 振幅>2% + 收阴</td></tr>
<tr><td>加速衰竭</td><td>exhaustion</td><td>近4天均涨>0.5% + 今日涨<均涨×0.3 + 放量</td></tr>
<tr><td>连阳停滞</td><td>yang_churn</td><td>近5天至少3阳 + 量>1.5×MA20 + 实体<0.6%</td></tr>
</table>
<h3>波谷信号</h3>
<table>
<tr><th>信号</th><th>英文名</th><th>规则</th></tr>
<tr><td>恐慌出清</td><td>panic</td><td>日跌>1.5% + 量>1.3×MA20 + 下影>实体×1.5</td></tr>
<tr><td>锤子线</td><td>hammer</td><td>下影>1.0% + 实体<下影 + 收阳</td></tr>
<tr><td>连续阴跌</td><td>fade</td><td>近5天至少4跌 + 量<0.8×MA20</td></tr>
<tr><td>十字星反转</td><td>doji_rev</td><td>前4天连跌 + 今日小实体收阳<0.8%</td></tr>
</table>

<h2>五、回测结果</h2>
<table>
<tr><th>指数</th><th>天数</th><th>波峰</th><th>波谷</th><th>峰召回率(5d)</th><th>谷召回率(5d)</th><th>峰误报</th><th>谷误报</th></tr>
<tr><td>中证全指</td><td>880</td><td>7</td><td>8</td><td>86% (6/7)</td><td>75% (6/8)</td><td>4.4%</td><td>4.0%</td></tr>
<tr><td>沪深300</td><td>880</td><td>6</td><td>9</td><td>67% (4/6)</td><td>89% (8/9)</td><td>3.8%</td><td>3.1%</td></tr>
<tr><td>创业板指</td><td>880</td><td>11</td><td>10</td><td>91% (10/11)</td><td>70% (7/10)</td><td>6.1%</td><td>5.2%</td></tr>
</table>

<p>其他台参数通用三个指数，无需单独调参。约90%时间判定为"波中"，10%时间有偏峰/偏谷预警。</p>

<h3>不同阈值灵敏度对比（中证全指880天）</h3>
<table>
<tr><th>阈值</th><th>峰召回率</th><th>谷召回率</th><th>峰天数</th><th>谷天数</th><th>占比</th></tr>
<tr><td>pk≥4/vl≥4</td><td>29%</td><td>0%</td><td>3天</td><td>2天</td><td>0.3%</td></tr>
<tr><td>pk≥3/vl≥3</td><td>86%</td><td>75%</td><td>55天</td><td>35天</td><td>6.3%</td></tr>
<tr><td>pk≥2/vl≥2</td><td>86%</td><td>100%</td><td>202天</td><td>164天</td><td>23%</td></tr>
</table>

<p>pk≥3/vl≥3（NEAR档）在召回率和误报率之间取得最佳平衡。</p>

<h2>六、三指数回测对比图</h2>
<img src="file://{CHART_PATH}" alt="三指数回测对比图" style="max-width:100%;margin:10px 0;">
<p style="color:#888;font-size:12px;">左侧：价格走势（红方块=真实波峰，绿方块=真实波谷，三角标记=V5预测位置）。右侧：评分走势（红线=pk_score，绿线=-vl_score，虚线=±3阈值）。</p>

<h2>七、关键统计发现</h2>
<ul>
<li>波峰时MA20乖离率中位数仅+2.30%（大部分在2~4%），说明不是高乖离率见顶</li>
<li>波谷时MA20乖离率中位数-4.42%（比峰更极端，大部分在-5~-3%）</li>
<li>乖离率>8%天数仅1.3%，固定阈值法会漏掉大量峰谷</li>
<li>变化速度比绝对值更重要：峰前3日变化中位数+1.27%，谷前-2.91%</li>
</ul>

<h2>八、实时判定调用</h2>
<p><code>judge_peak_valley(klines)</code> 在每日复盘中自动调用，基于最新K线数据实时输出5档判定结果。</p>
<p>数据源：sh000985（中证全指，腾讯财经API）。代码：<code>generate_review_data.py</code> → <code>judge_peak_valley()</code></p>

</body></html>'''

# 生成HTML转PDF
tmp = tempfile.mkdtemp()
html_path = os.path.join(tmp, 'input.html')
with open(html_path, 'w') as f:
    f.write(gen_html())

subprocess.run([
    'wkhtmltopdf',
    '--encoding', 'utf-8',
    '--page-size', 'A4',
    '--margin-top', '15mm',
    '--margin-bottom', '15mm',
    '--margin-left', '15mm',
    '--margin-right', '15mm',
    '--enable-local-file-access',  # 允许加载本地图片
    '--no-stop-slow-scripts',
    html_path,
    OUTPUT
], check=True, timeout=30)

shutil.rmtree(tmp)
print(f'OK: {OUTPUT}')
sz = os.path.getsize(OUTPUT)
print(f'Size: {sz} bytes')
