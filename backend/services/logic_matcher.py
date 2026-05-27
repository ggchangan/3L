"""
逻辑标签匹配引擎

方案C：关键词粗筛 + LLM语义匹配（兜底）
P0先实现关键词匹配，LLM部分留接口后续扩展
"""
import re


class LogicMatcher:
    """逻辑标签匹配器"""

    def __init__(self, tags):
        """
        Args:
            tags: 逻辑标签列表，每项含 id, name, related_industries, related_stocks
        """
        self._tags = tags or []

    def keyword_match(self, code, name, industry):
        """关键词粗筛（方案A）

        Args:
            code: 股票代码
            name: 股票名称
            industry: 行业名

        Returns:
            [{tag_id, tag_name, confidence, reason}, ...]
        """
        results = []

        for tag in self._tags:
            score = 0
            reasons = []

            # ① 匹配关联个股
            related_stocks = tag.get('related_stocks', [])
            if code and code in related_stocks:
                score += 60
                reasons.append('个股匹配')

            # ② 匹配行业
            related_industries = tag.get('related_industries', [])
            if industry:
                for ind in related_industries:
                    if industry == ind or (len(industry) >= 2 and ind and (
                            industry in ind or ind in industry)):
                        score += 40
                        reasons.append(f'行业匹配({ind})')
                        break

            # ③ 匹配标签名称关键词
            tag_name = tag.get('name', '')
            if industry and tag_name:
                # 检查行业是否包含在标签名中，或标签名包含行业关键词
                tag_keywords = re.split(r'[／/、,，\s]+', tag_name)
                for kw in tag_keywords:
                    if len(kw) >= 2 and industry and (
                            kw in industry or industry in kw):
                        score += 30
                        reasons.append(f'关键词匹配({kw})')
                        break

            if score > 0:
                results.append({
                    'tag_id': tag['id'],
                    'tag_name': tag.get('name', ''),
                    'confidence': min(score, 99),
                    'reason': '；'.join(reasons) if reasons else '模糊匹配',
                })

        # 按置信度降序
        results.sort(key=lambda r: r['confidence'], reverse=True)
        return results

    def llm_match(self, code, name, industry):
        """LLM语义匹配（方案B）

        P0暂不实现，返回空列表。后续对接LLM API。
        """
        return []

    def match_all(self, code, name, industry):
        """方案C：混合匹配

        先关键词，未命中或低置信度走LLM兜底。
        P0：仅关键词匹配（方案A），LLM留接口。
        """
        results = self.keyword_match(code, name, industry)

        # 如果关键词无结果或有低置信度结果，走LLM兜底
        if not results or max(r['confidence'] for r in results) < 30:
            llm_results = self.llm_match(code, name, industry)
            if llm_results:
                results.extend(llm_results)

        return results
