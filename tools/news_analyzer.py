"""
新闻分析引擎
负责逻辑分析、交叉验证和结论生成
"""
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    """分析结果"""
    verdict: str  # 真实/虚假/部分真实/无法验证
    confidence: float  # 置信度 0-100
    key_findings: list[str]  # 主要发现
    detailed_analysis: str  # 详细分析
    recommendations: list[str]  # 建议


class NewsAnalyzer:
    """新闻分析引擎"""

    def __init__(self):
        pass

    def analyze(
        self,
        claim: str,
        evaluated_sources: list[dict],
        original_text: str = ""
    ) -> AnalysisResult:
        """
        分析新闻并生成结论

        Args:
            claim: 待验证声明
            evaluated_sources: 已评估的来源列表
            original_text: 原始新闻文本

        Returns:
            AnalysisResult
        """
        # 1. 计算来源统计
        source_stats = self._calculate_source_stats(evaluated_sources)

        # 2. 交叉验证
        consistency = self._cross_validate(evaluated_sources)

        # 3. 确定结论
        verdict, confidence = self._determine_verdict(source_stats, consistency)

        # 4. 生成主要发现
        key_findings = self._generate_key_findings(
            source_stats, consistency, evaluated_sources
        )

        # 5. 生成详细分析
        detailed_analysis = self._generate_detailed_analysis(
            claim, source_stats, consistency, evaluated_sources
        )

        # 6. 生成建议
        recommendations = self._generate_recommendations(verdict, confidence)

        return AnalysisResult(
            verdict=verdict,
            confidence=confidence,
            key_findings=key_findings,
            detailed_analysis=detailed_analysis,
            recommendations=recommendations
        )

    def _calculate_source_stats(self, sources: list[dict]) -> dict:
        """计算来源统计"""
        if not sources:
            return {"total": 0, "high": 0, "medium": 0, "low": 0, "avg_score": 0}

        high = sum(1 for s in sources if s.get("credibility_score", 0) >= 80)
        medium = sum(1 for s in sources if 50 <= s.get("credibility_score", 0) < 80)
        low = sum(1 for s in sources if s.get("credibility_score", 0) < 50)
        avg_score = sum(s.get("credibility_score", 0) for s in sources) / len(sources)

        return {
            "total": len(sources),
            "high": high,
            "medium": medium,
            "low": low,
            "avg_score": avg_score
        }

    def _cross_validate(self, sources: list[dict]) -> dict:
        """交叉验证来源一致性"""
        if len(sources) < 2:
            return {"consistent": False, "score": 50, "reason": "来源不足"}

        # 统计各级别来源数量
        high_credibility = [s for s in sources if s.get("credibility_score", 0) >= 80]
        medium_credibility = [s for s in sources if 50 <= s.get("credibility_score", 0) < 80]
        total_credible = len(high_credibility) + len(medium_credibility)

        # 多个权威来源
        if len(high_credibility) >= 2:
            return {"consistent": True, "score": 95, "reason": "多个权威来源一致报道"}

        # 1个权威 + 多个中等
        if len(high_credibility) == 1 and len(medium_credibility) >= 2:
            return {"consistent": True, "score": 88, "reason": "权威来源报道，多个中等来源佐证"}

        # 1个权威来源
        if len(high_credibility) == 1:
            return {"consistent": True, "score": 75, "reason": "有权威来源报道"}

        # 多个中等可信度来源一致报道（关键改进）
        if len(medium_credibility) >= 4:
            return {"consistent": True, "score": 85, "reason": "多个中等可信度来源一致报道"}
        if len(medium_credibility) >= 3:
            return {"consistent": True, "score": 78, "reason": "3个以上中等可信度来源报道"}
        if len(medium_credibility) >= 2:
            return {"consistent": True, "score": 70, "reason": "多个中等可信度来源报道"}

        # 有一些可信来源
        if total_credible >= 2:
            return {"consistent": True, "score": 60, "reason": "有多个来源报道"}

        # 来源较少或可信度较低
        if len(sources) >= 3:
            return {"consistent": True, "score": 55, "reason": "多个来源报道但可信度一般"}

        return {"consistent": False, "score": 40, "reason": "缺乏可信来源"}

    def _determine_verdict(
        self,
        source_stats: dict,
        consistency: dict
    ) -> tuple[str, float]:
        """确定验证结论"""
        avg_score = source_stats.get("avg_score", 0)
        consistency_score = consistency.get("score", 50)
        total_sources = source_stats.get("total", 0)
        high_count = source_stats.get("high", 0)
        medium_count = source_stats.get("medium", 0)

        # 基础综合评分
        overall = avg_score * 0.5 + consistency_score * 0.5

        # 来源数量加成（多个来源一致报道提升可信度）
        source_bonus = 0
        if total_sources >= 5:
            source_bonus = 10
        elif total_sources >= 3:
            source_bonus = 5

        # 可信来源数量加成
        credible_count = high_count + medium_count
        if credible_count >= 4:
            source_bonus += 8
        elif credible_count >= 3:
            source_bonus += 5
        elif credible_count >= 2:
            source_bonus += 3

        overall = min(100, overall + source_bonus)

        if overall >= 75:
            return "真实", overall
        elif overall >= 55:
            return "部分真实", overall
        elif overall >= 35:
            return "无法验证", overall
        else:
            return "可能虚假", overall

    def _generate_key_findings(
        self,
        source_stats: dict,
        consistency: dict,
        sources: list[dict]
    ) -> list[str]:
        """生成主要发现"""
        findings = []

        # 来源数量
        findings.append(f"共找到 {source_stats['total']} 个相关来源")

        # 权威来源
        if source_stats["high"] > 0:
            findings.append(f"其中 {source_stats['high']} 个为高可信度来源")
        else:
            findings.append("未找到高可信度来源")

        # 一致性
        if consistency.get("reason"):
            findings.append(consistency["reason"])

        # 来源分布
        if source_stats["low"] > source_stats["high"]:
            findings.append("低可信度来源占比较高，需谨慎对待")

        return findings

    def _generate_detailed_analysis(
        self,
        claim: str,
        source_stats: dict,
        consistency: dict,
        sources: list[dict]
    ) -> str:
        """生成详细分析"""
        lines = []

        # 截断过长的声明
        claim_display = claim[:50] + "..." if len(claim) > 50 else claim
        lines.append(f"针对「{claim_display}」的验证分析：")
        lines.append("")

        # 来源分析
        lines.append(f"1. 来源分析：共检索到 {source_stats['total']} 个相关来源，")
        lines.append(f"   其中高可信度 {source_stats['high']} 个，中等可信度 {source_stats['medium']} 个，")
        lines.append(f"   低可信度 {source_stats['low']} 个。")
        lines.append("")

        # 交叉验证
        lines.append(f"2. 交叉验证：{consistency.get('reason', '无法确定')}")
        lines.append(f"   一致性评分：{consistency.get('score', 0):.0f}/100")
        lines.append("")

        # 综合评估
        lines.append(f"3. 综合评估：来源平均可信度为 {source_stats['avg_score']:.1f}/100")

        # 主要来源列表
        if sources:
            lines.append("")
            lines.append("4. 主要来源：")
            for i, source in enumerate(sources[:5], 1):
                name = source.get("source_name", "Unknown")
                score = source.get("credibility_score", 0)
                title = source.get("title", "")[:30]
                lines.append(f"   {i}. {name} ({score:.0f}分) - {title}...")

        return "\n".join(lines)

    def _generate_recommendations(
        self,
        verdict: str,
        confidence: float
    ) -> list[str]:
        """生成建议"""
        recommendations = []

        if verdict == "真实":
            recommendations.append("该信息来源可靠，可以正常分享")
            recommendations.append("建议关注后续报道以获取更多细节")
        elif verdict == "部分真实":
            recommendations.append("该信息部分内容可能存在偏差")
            recommendations.append("建议查阅原始来源获取完整信息")
            recommendations.append("分享时注明信息可能不完整")
        elif verdict == "无法验证":
            recommendations.append("该信息暂时无法确认真假")
            recommendations.append("建议等待更多权威来源报道")
            recommendations.append("暂不建议转发传播")
        else:
            recommendations.append("该信息可信度较低，请谨慎对待")
            recommendations.append("不建议转发传播")
            recommendations.append("如有疑问可向官方渠道求证")

        return recommendations

    def quick_analyze(self, sources: list[dict]) -> dict:
        """
        快速分析（仅返回基本结论）

        Args:
            sources: 已评估的来源列表

        Returns:
            包含 verdict 和 score 的字典
        """
        source_stats = self._calculate_source_stats(sources)
        consistency = self._cross_validate(sources)
        verdict, confidence = self._determine_verdict(source_stats, consistency)

        return {
            "verdict": verdict,
            "confidence": confidence,
            "source_count": source_stats["total"],
            "high_credibility_count": source_stats["high"],
        }
