"""
新闻验证工具类
整合所有验证组件，提供统一的验证接口
"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import WorkspacePlugin

from astrbot.api import logger

from ..credibility import CredibilityEvaluator, SourceRegistry
from .fact_extractor import FactExtractor, FactPoint
from .news_analyzer import AnalysisResult, NewsAnalyzer
from .report_generator import ReportGenerator
from .screenshot_tool import ScreenshotTool


@dataclass
class SearchResult:
    """搜索结果"""
    url: str
    title: str
    snippet: str
    source_name: str = ""
    credibility_score: float = 50.0
    supports_claim: bool = False


@dataclass
class VerificationResult:
    """验证结果"""
    claim: str
    verdict: str
    credibility_score: float
    source_analysis: list[dict]
    key_findings: list[str]
    detailed_analysis: str
    recommendations: list[str]
    report_path: str | None = None
    screenshots: list[str] = field(default_factory=list)
    fact_points: list[FactPoint] = field(default_factory=list)


class FactCheckTools:
    """新闻验证工具类"""

    def __init__(self, plugin: "WorkspacePlugin"):
        self.plugin = plugin
        self.config = plugin.config

        # 初始化各组件
        self.evaluator = CredibilityEvaluator(plugin.config)
        self.registry = SourceRegistry()
        self.fact_extractor = FactExtractor(plugin)
        self.news_analyzer = NewsAnalyzer()
        self.report_generator = ReportGenerator(plugin)
        self.screenshot_tool = ScreenshotTool(plugin)

        # 配置
        self.max_search_results = plugin.config.get("max_search_results", 10)
        self.enable_screenshots = plugin.config.get("enable_screenshots", True)
        self.max_screenshots = plugin.config.get("max_screenshots", 3)

    def extract_facts(self, text: str, min_verifiability: str = "medium") -> list[FactPoint]:
        """
        从文本中提取可验证的事实点

        Args:
            text: 新闻文本
            min_verifiability: 最低可验证性要求 (high/medium/low)

        Returns:
            事实点列表
        """
        facts = self.fact_extractor.extract_facts(text)
        return self.fact_extractor.filter_verifiable_facts(facts, min_verifiability)

    def get_search_queries(self, facts: list[FactPoint]) -> list[str]:
        """
        从事实点生成搜索查询

        Args:
            facts: 事实点列表

        Returns:
            搜索查询列表
        """
        return [fact.search_query for fact in facts if fact.search_query]

    def evaluate_search_results(
        self,
        results: list[dict],
        claim: str = ""
    ) -> list[SearchResult]:
        """
        评估搜索结果的可信度

        Args:
            results: 原始搜索结果列表
            claim: 原始声明（用于判断是否支持）

        Returns:
            评估后的搜索结果列表
        """
        evaluated = []

        for result in results[:self.max_search_results]:
            url = result.get("url", "")
            title = result.get("title", "")
            snippet = result.get("snippet", result.get("description", ""))

            # 评估来源可信度
            score, source_info = self.evaluator.evaluate_source(url)

            # 简单判断是否支持声明（基于标题和摘要）
            supports = self._check_support(title, snippet, claim) if claim else False

            evaluated.append(SearchResult(
                url=url,
                title=title,
                snippet=snippet,
                source_name=source_info.name,
                credibility_score=score,
                supports_claim=supports
            ))

        # 按可信度排序
        evaluated.sort(key=lambda x: x.credibility_score, reverse=True)
        return evaluated

    async def evaluate_search_results_with_dynamic(
        self,
        results: list[dict],
        claim: str = ""
    ) -> list[SearchResult]:
        """
        评估搜索结果的可信度（包含动态检查）

        Args:
            results: 原始搜索结果列表
            claim: 原始声明

        Returns:
            评估后的搜索结果列表
        """
        evaluated = []

        for result in results[:self.max_search_results]:
            url = result.get("url", "")
            title = result.get("title", "")
            snippet = result.get("snippet", result.get("description", ""))

            try:
                # 动态评估来源可信度
                score, source_info, dynamic_result = await self.evaluator.evaluate_source_with_dynamic(url)
            except Exception as e:
                logger.warning(f"动态评估失败 {url}: {e}")
                score, source_info = self.evaluator.evaluate_source(url)

            supports = self._check_support(title, snippet, claim) if claim else False

            evaluated.append(SearchResult(
                url=url,
                title=title,
                snippet=snippet,
                source_name=source_info.name,
                credibility_score=score,
                supports_claim=supports
            ))

        evaluated.sort(key=lambda x: x.credibility_score, reverse=True)
        return evaluated

    def _check_support(self, title: str, snippet: str, claim: str) -> bool:
        """简单检查内容是否支持声明"""
        if not claim:
            return False

        # 提取声明中的关键词
        claim_words = set(claim)
        content = title + " " + snippet

        # 计算关键词匹配度
        match_count = sum(1 for word in claim_words if word in content)
        match_rate = match_count / len(claim_words) if claim_words else 0

        # 检查是否包含否定词
        negative_words = ["假", "谣", "辟谣", "不实", "虚假", "错误", "否认", "澄清"]
        has_negative = any(word in content for word in negative_words)

        # 如果匹配度高且没有否定词，认为支持
        return match_rate > 0.3 and not has_negative

    def analyze_results(
        self,
        claim: str,
        evaluated_results: list[SearchResult],
        original_text: str = ""
    ) -> AnalysisResult:
        """
        分析评估后的搜索结果

        Args:
            claim: 待验证声明
            evaluated_results: 评估后的搜索结果
            original_text: 原始新闻文本

        Returns:
            分析结果
        """
        # 转换为分析器需要的格式
        sources = [
            {
                "url": r.url,
                "title": r.title,
                "snippet": r.snippet,
                "source_name": r.source_name,
                "credibility_score": r.credibility_score,
                "supports": r.supports_claim
            }
            for r in evaluated_results
        ]

        return self.news_analyzer.analyze(claim, sources, original_text)

    async def take_evidence_screenshots(
        self,
        urls: list[str],
        workspace: str
    ) -> list[str]:
        """
        对证据网页进行截图

        Args:
            urls: URL 列表
            workspace: 工作区路径

        Returns:
            截图文件路径列表
        """
        if not self.enable_screenshots:
            return []

        screenshots = []
        results = await self.screenshot_tool.batch_screenshot(
            urls[:self.max_screenshots],
            workspace
        )

        for result in results:
            if result.get("path"):
                screenshots.append(result["path"])
            elif result.get("error"):
                logger.warning(f"截图失败 {result['url']}: {result['error']}")

        return screenshots

    async def generate_report(
        self,
        claim: str,
        analysis: AnalysisResult,
        evaluated_results: list[SearchResult],
        workspace: str,
        screenshots: list[str] = None
    ) -> str:
        """
        生成验证报告

        Args:
            claim: 待验证声明
            analysis: 分析结果
            evaluated_results: 评估后的搜索结果
            workspace: 工作区路径
            screenshots: 截图文件路径列表

        Returns:
            报告文件路径
        """
        source_analysis = [
            {
                "url": r.url,
                "title": r.title,
                "source_name": r.source_name,
                "credibility_score": r.credibility_score
            }
            for r in evaluated_results
        ]

        return await self.report_generator.generate_pdf_report(
            claim=claim,
            verdict=analysis.verdict,
            credibility_score=analysis.confidence,
            source_analysis=source_analysis,
            detailed_analysis=analysis.detailed_analysis,
            recommendations=analysis.recommendations,
            workspace=workspace,
            screenshots=screenshots
        )

    async def verify_claim(
        self,
        claim: str,
        search_results: list[dict],
        workspace: str,
        original_text: str = "",
        generate_report: bool = True,
        take_screenshots: bool = True
    ) -> VerificationResult:
        """
        完整的声明验证流程

        Args:
            claim: 待验证声明
            search_results: 搜索结果
            workspace: 工作区路径
            original_text: 原始新闻文本
            generate_report: 是否生成报告
            take_screenshots: 是否截图

        Returns:
            验证结果
        """
        # 1. 评估搜索结果
        evaluated = await self.evaluate_search_results_with_dynamic(search_results, claim)

        # 2. 分析结果
        analysis = self.analyze_results(claim, evaluated, original_text)

        # 3. 截图（可选）
        screenshots = []
        if take_screenshots and self.enable_screenshots:
            # 选择高可信度来源进行截图
            high_credibility_urls = [
                r.url for r in evaluated
                if r.credibility_score >= 70
            ][:self.max_screenshots]

            if high_credibility_urls:
                screenshots = await self.take_evidence_screenshots(
                    high_credibility_urls, workspace
                )

        # 4. 生成报告（可选）
        report_path = None
        if generate_report:
            report_path = await self.generate_report(
                claim, analysis, evaluated, workspace, screenshots
            )

        # 5. 构建结果
        source_analysis = [
            {
                "url": r.url,
                "title": r.title,
                "source_name": r.source_name,
                "credibility_score": r.credibility_score,
                "supports": r.supports_claim
            }
            for r in evaluated
        ]

        return VerificationResult(
            claim=claim,
            verdict=analysis.verdict,
            credibility_score=analysis.confidence,
            source_analysis=source_analysis,
            key_findings=analysis.key_findings,
            detailed_analysis=analysis.detailed_analysis,
            recommendations=analysis.recommendations,
            report_path=report_path,
            screenshots=screenshots
        )

    async def verify_news(
        self,
        news_text: str,
        search_results: list[dict],
        workspace: str,
        generate_report: bool = True,
        take_screenshots: bool = True
    ) -> VerificationResult:
        """
        完整的新闻验证流程（包含事实点提取）

        Args:
            news_text: 新闻文本
            search_results: 搜索结果
            workspace: 工作区路径
            generate_report: 是否生成报告
            take_screenshots: 是否截图

        Returns:
            验证结果
        """
        # 1. 提取事实点
        facts = self.extract_facts(news_text, min_verifiability="medium")

        # 2. 使用新闻文本作为声明进行验证
        claim = news_text[:200] if len(news_text) > 200 else news_text

        # 3. 执行验证
        result = await self.verify_claim(
            claim=claim,
            search_results=search_results,
            workspace=workspace,
            original_text=news_text,
            generate_report=generate_report,
            take_screenshots=take_screenshots
        )

        # 4. 附加事实点信息
        result.fact_points = facts

        return result

    def format_brief_result(self, result: VerificationResult) -> str:
        """
        格式化简要结果（用于消息回复）

        Args:
            result: 验证结果

        Returns:
            格式化的文本
        """
        lines = [
            f"验证结论: {result.verdict}",
            f"可信度评分: {result.credibility_score:.0f}/100",
            "",
            "主要发现:",
        ]

        for finding in result.key_findings[:3]:
            lines.append(f"• {finding}")

        lines.append("")

        if result.recommendations:
            lines.append("建议:")
            for rec in result.recommendations[:2]:
                lines.append(f"• {rec}")

        if result.report_path:
            lines.append("")
            lines.append("详细报告已生成")

        return "\n".join(lines)

    def get_verification_plan(self, news_text: str) -> dict:
        """
        获取验证计划（用于展示给用户）

        Args:
            news_text: 新闻文本

        Returns:
            验证计划字典
        """
        facts = self.extract_facts(news_text)
        return self.fact_extractor.generate_verification_plan(facts)
