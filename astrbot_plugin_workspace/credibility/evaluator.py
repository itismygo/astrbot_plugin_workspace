"""
可信度评估器
综合静态和动态评估，计算来源可信度评分
"""
from dataclasses import dataclass, field

from .dynamic_checker import DynamicChecker
from .source_registry import CredibilityLevel, SourceRegistry


@dataclass
class CredibilityScore:
    """可信度评分结果"""
    overall_score: float
    source_score: float
    consistency_score: float
    language_score: float
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "overall_score": self.overall_score,
            "source_score": self.source_score,
            "consistency_score": self.consistency_score,
            "language_score": self.language_score,
            "details": self.details or {}
        }


@dataclass
class EvaluationConfig:
    """评估配置"""
    source_weight: float = 0.4
    consistency_weight: float = 0.4
    language_weight: float = 0.2
    min_sources_for_verification: int = 3
    enable_dynamic_check: bool = True


class CredibilityEvaluator:
    """可信度评估器"""

    def __init__(self, config: dict = None):
        self.registry = SourceRegistry()
        self.config = EvaluationConfig(**(config or {}))
        self.dynamic_checker = DynamicChecker(config)

        # 情绪化词汇列表（中文）
        self.emotional_words_cn = [
            "震惊", "惊爆", "重磅", "突发", "紧急", "速看", "疯传",
            "不转不是中国人", "必看", "太可怕了", "细思极恐", "吓人",
            "恐怖", "惊天", "爆炸性", "独家", "内幕", "揭秘", "真相",
            "万万没想到", "竟然", "居然", "原来", "终于", "刚刚",
        ]

        # 情绪化词汇列表（英文）
        self.emotional_words_en = [
            "shocking", "breaking", "urgent", "must see", "unbelievable",
            "incredible", "amazing", "terrifying", "horrifying", "explosive",
            "exclusive", "revealed", "exposed", "truth", "finally",
        ]

        # 可信度等级对应的基础分数
        self.level_scores = {
            CredibilityLevel.HIGHLY_TRUSTED: 100,
            CredibilityLevel.TRUSTED: 80,
            CredibilityLevel.MODERATE: 60,
            CredibilityLevel.LOW: 30,
            CredibilityLevel.UNTRUSTED: 10,
            CredibilityLevel.UNKNOWN: 50,
        }

    def evaluate_source(self, url: str) -> tuple:
        """
        评估单个来源的可信度

        Args:
            url: 来源 URL

        Returns:
            (score, source_info) 元组
        """
        source_info = self.registry.get_credibility(url)
        score = self.level_scores.get(source_info.level, 50)
        return score, source_info

    async def evaluate_source_with_dynamic(self, url: str) -> tuple:
        """
        评估单个来源的可信度（包含动态检查）

        Args:
            url: 来源 URL

        Returns:
            (score, source_info, dynamic_result) 元组
        """
        # 静态评估
        source_info = self.registry.get_credibility(url)
        base_score = self.level_scores.get(source_info.level, 50)

        # 动态评估
        dynamic_result = None
        if self.config.enable_dynamic_check:
            dynamic_result = await self.dynamic_checker.check_all(url)
            # 应用动态评分调整
            final_score = min(100, max(0, base_score + dynamic_result.score_adjustment))
        else:
            final_score = base_score

        return final_score, source_info, dynamic_result

    def evaluate_consistency(self, claims: list[dict]) -> float:
        """
        评估多个来源的一致性

        Args:
            claims: 声明列表，每个包含 supports 字段表示是否支持原声明

        Returns:
            一致性评分 (0-100)
        """
        if len(claims) < 2:
            return 50.0

        # 计算支持率
        supporting = sum(1 for c in claims if c.get("supports", False))
        total = len(claims)
        support_rate = supporting / total

        # 来源数量奖励（更多来源验证更可靠）
        source_bonus = min(10, (total - 2) * 2)

        return min(100, support_rate * 90 + source_bonus)

    def evaluate_language(self, text: str) -> float:
        """
        评估文本的语言客观性

        Args:
            text: 待评估文本

        Returns:
            语言客观性评分 (0-100)
        """
        text_lower = text.lower()

        # 统计情绪化词汇
        emotional_count = 0
        for word in self.emotional_words_cn + self.emotional_words_en:
            if word.lower() in text_lower:
                emotional_count += 1

        # 统计感叹号
        exclamation_count = text.count("!") + text.count("！")

        # 统计问号（过多问号可能是标题党）
        question_count = text.count("?") + text.count("？")

        # 计算扣分
        deduction = (
            emotional_count * 10 +
            exclamation_count * 5 +
            max(0, question_count - 2) * 3
        )

        return max(0, 100 - deduction)

    def calculate_overall_score(
        self,
        source_scores: list[float],
        consistency_score: float,
        language_score: float
    ) -> CredibilityScore:
        """
        计算综合可信度评分

        Args:
            source_scores: 各来源的评分列表
            consistency_score: 一致性评分
            language_score: 语言客观性评分

        Returns:
            CredibilityScore 对象
        """
        # 计算来源平均分
        avg_source_score = sum(source_scores) / len(source_scores) if source_scores else 50

        # 加权计算综合分
        overall = (
            avg_source_score * self.config.source_weight +
            consistency_score * self.config.consistency_weight +
            language_score * self.config.language_weight
        )

        return CredibilityScore(
            overall_score=round(overall, 1),
            source_score=round(avg_source_score, 1),
            consistency_score=round(consistency_score, 1),
            language_score=round(language_score, 1),
            details={
                "source_count": len(source_scores),
                "weights": {
                    "source": self.config.source_weight,
                    "consistency": self.config.consistency_weight,
                    "language": self.config.language_weight,
                }
            }
        )

    def get_verdict(self, score: float) -> str:
        """
        根据评分获取验证结论

        Args:
            score: 综合评分

        Returns:
            验证结论字符串
        """
        if score >= 80:
            return "真实"
        elif score >= 60:
            return "部分真实"
        elif score >= 40:
            return "无法验证"
        else:
            return "可能虚假"

    def get_recommendation(self, score: float) -> list[str]:
        """
        根据评分获取建议

        Args:
            score: 综合评分

        Returns:
            建议列表
        """
        if score >= 80:
            return [
                "该信息来源可靠，可以正常分享",
                "建议关注后续报道以获取更多细节"
            ]
        elif score >= 60:
            return [
                "该信息部分内容可能存在偏差",
                "建议查阅原始来源获取完整信息",
                "分享时注明信息可能不完整"
            ]
        elif score >= 40:
            return [
                "该信息暂时无法确认真假",
                "建议等待更多权威来源报道",
                "暂不建议转发传播"
            ]
        else:
            return [
                "该信息可信度较低，请谨慎对待",
                "不建议转发传播",
                "如有疑问可向官方渠道求证"
            ]
