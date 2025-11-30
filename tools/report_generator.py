"""
PDF 报告生成器
生成新闻验证报告
"""
import os
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import WorkspacePlugin

from astrbot.api import logger


class ReportGenerator:
    """PDF 报告生成器"""

    def __init__(self, plugin: "WorkspacePlugin"):
        self.plugin = plugin

    async def generate_pdf_report(
        self,
        claim: str,
        verdict: str,
        credibility_score: float,
        source_analysis: list[dict],
        detailed_analysis: str,
        recommendations: list[str],
        workspace: str,
        screenshots: list[str] = None
    ) -> str:
        """
        生成 PDF 验证报告

        Args:
            claim: 待验证声明
            verdict: 验证结论
            credibility_score: 可信度评分
            source_analysis: 来源分析列表
            detailed_analysis: 详细分析
            recommendations: 建议列表
            workspace: 工作区路径
            screenshots: 截图文件路径列表

        Returns:
            PDF 文件路径
        """
        # 生成 HTML 内容
        html_content = self._build_html_report(
            claim=claim,
            verdict=verdict,
            credibility_score=credibility_score,
            source_analysis=source_analysis,
            detailed_analysis=detailed_analysis,
            recommendations=recommendations,
            screenshots=screenshots or []
        )

        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(workspace, "outputs")
        os.makedirs(output_dir, exist_ok=True)
        pdf_path = os.path.join(output_dir, f"fact_check_report_{timestamp}.pdf")

        # 渲染为 PDF
        result_path = await self._render_to_pdf(html_content, pdf_path)

        return result_path

    def _build_html_report(
        self,
        claim: str,
        verdict: str,
        credibility_score: float,
        source_analysis: list[dict],
        detailed_analysis: str,
        recommendations: list[str],
        screenshots: list[str] = None
    ) -> str:
        """构建 HTML 报告"""
        # 根据评分确定颜色和文字
        if credibility_score >= 80:
            score_color = "#28a745"  # 绿色
            verdict_text = "可信度较高"
        elif credibility_score >= 60:
            score_color = "#ffc107"  # 黄色
            verdict_text = "需进一步核实"
        elif credibility_score >= 40:
            score_color = "#fd7e14"  # 橙色
            verdict_text = "可信度存疑"
        else:
            score_color = "#dc3545"  # 红色
            verdict_text = "可信度较低"

        # 来源列表 HTML
        sources_html = ""
        for i, source in enumerate(source_analysis[:10], 1):
            source_name = source.get("source_name", "Unknown")
            score = source.get("credibility_score", 0)
            title = source.get("title", "")[:40]
            url = source.get("url", "")
            sources_html += f"""
            <tr>
                <td>{i}</td>
                <td>{source_name}</td>
                <td>{score:.0f}</td>
                <td><a href="{url}" target="_blank">{title}...</a></td>
            </tr>
            """

        # 建议列表 HTML
        recommendations_html = "".join(f"<li>{r}</li>" for r in recommendations)

        # 截图 HTML
        screenshots_html = ""
        if screenshots:
            screenshots_html = '<div class="section"><div class="section-title">证据截图</div>'
            for i, screenshot_path in enumerate(screenshots, 1):
                if os.path.exists(screenshot_path):
                    # 使用 base64 编码嵌入图片
                    import base64
                    with open(screenshot_path, "rb") as f:
                        img_data = base64.b64encode(f.read()).decode()
                    screenshots_html += f"""
                    <div class="screenshot">
                        <p>截图 {i}</p>
                        <img src="data:image/png;base64,{img_data}" alt="证据截图 {i}" style="max-width: 100%; border: 1px solid #ddd;">
                    </div>
                    """
            screenshots_html += "</div>"

        # 转义详细分析中的换行
        detailed_analysis_html = detailed_analysis.replace("\n", "<br>")

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>新闻验证报告</title>
            <style>
                body {{
                    font-family: "Microsoft YaHei", "SimHei", sans-serif;
                    padding: 20px;
                    max-width: 800px;
                    margin: 0 auto;
                    color: #333;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                    border-bottom: 2px solid #333;
                    padding-bottom: 20px;
                }}
                .header h1 {{
                    margin-bottom: 10px;
                    color: #333;
                }}
                .score-box {{
                    background: {score_color};
                    color: white;
                    padding: 20px;
                    border-radius: 10px;
                    text-align: center;
                    margin: 20px 0;
                }}
                .score {{
                    font-size: 48px;
                    font-weight: bold;
                }}
                .verdict {{
                    font-size: 24px;
                    margin-top: 10px;
                }}
                .section {{
                    margin: 20px 0;
                }}
                .section-title {{
                    font-size: 18px;
                    font-weight: bold;
                    border-bottom: 2px solid #333;
                    padding-bottom: 5px;
                    margin-bottom: 15px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 10px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background: #f5f5f5;
                }}
                .claim {{
                    background: #f9f9f9;
                    padding: 15px;
                    border-left: 4px solid #007bff;
                    margin: 10px 0;
                }}
                .analysis {{
                    line-height: 1.8;
                    background: #fafafa;
                    padding: 15px;
                    border-radius: 5px;
                }}
                .footer {{
                    text-align: center;
                    color: #666;
                    margin-top: 30px;
                    font-size: 12px;
                    border-top: 1px solid #ddd;
                    padding-top: 20px;
                }}
                ul {{
                    padding-left: 20px;
                }}
                li {{
                    margin: 5px 0;
                }}
                a {{
                    color: #007bff;
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                .screenshot {{
                    margin: 15px 0;
                    padding: 10px;
                    background: #f9f9f9;
                    border-radius: 5px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>新闻验证报告</h1>
                <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
            </div>

            <div class="section">
                <div class="section-title">待验证内容</div>
                <div class="claim">{claim}</div>
            </div>

            <div class="score-box">
                <div class="score">{credibility_score:.0f}/100</div>
                <div class="verdict">{verdict_text}</div>
            </div>

            <div class="section">
                <div class="section-title">验证结论</div>
                <p><strong>{verdict}</strong></p>
            </div>

            <div class="section">
                <div class="section-title">来源分析</div>
                <table>
                    <tr>
                        <th>#</th>
                        <th>来源</th>
                        <th>可信度</th>
                        <th>标题</th>
                    </tr>
                    {sources_html}
                </table>
            </div>

            <div class="section">
                <div class="section-title">详细分析</div>
                <div class="analysis">{detailed_analysis_html}</div>
            </div>

            <div class="section">
                <div class="section-title">建议</div>
                <ul>{recommendations_html}</ul>
            </div>

            {screenshots_html}

            <div class="footer">
                <p>本报告由 AI 自动生成，仅供参考</p>
                <p>请结合多方信息综合判断</p>
            </div>
        </body>
        </html>
        """
        return html

    async def _render_to_pdf(self, html_content: str, output_path: str) -> str:
        """渲染 HTML 为 PDF"""
        # 方案1: 使用 weasyprint
        try:
            from weasyprint import HTML
            HTML(string=html_content).write_pdf(output_path)
            logger.info(f"PDF 报告已生成: {output_path}")
            return output_path
        except ImportError:
            logger.warning("weasyprint 未安装，降级为 HTML 格式")
        except Exception as e:
            logger.error(f"weasyprint 生成 PDF 失败: {e}")

        # 降级为保存 HTML
        html_path = output_path.replace(".pdf", ".html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"HTML 报告已生成: {html_path}")
        return html_path

    def generate_brief_conclusion(
        self,
        verdict: str,
        credibility_score: float,
        key_findings: list[str]
    ) -> str:
        """
        生成精简结论（用于消息回复）

        Args:
            verdict: 验证结论
            credibility_score: 可信度评分
            key_findings: 主要发现列表

        Returns:
            精简结论文本
        """
        lines = [
            f"验证结论: {verdict}",
            f"可信度评分: {credibility_score:.0f}/100",
            "",
            "主要发现:",
        ]
        for finding in key_findings[:3]:
            lines.append(f"- {finding}")

        lines.append("")
        lines.append("详细报告已生成为 PDF 文件")

        return "\n".join(lines)

    def generate_text_report(
        self,
        claim: str,
        verdict: str,
        credibility_score: float,
        source_analysis: list[dict],
        detailed_analysis: str,
        recommendations: list[str]
    ) -> str:
        """
        生成纯文本报告

        Args:
            claim: 待验证声明
            verdict: 验证结论
            credibility_score: 可信度评分
            source_analysis: 来源分析列表
            detailed_analysis: 详细分析
            recommendations: 建议列表

        Returns:
            纯文本报告
        """
        lines = [
            "新闻验证报告",
            "=" * 40,
            "",
            f"待验证内容: {claim}",
            "",
            f"验证结论: {verdict}",
            f"可信度评分: {credibility_score:.0f}/100",
            "",
            "来源分析:",
        ]

        for i, source in enumerate(source_analysis[:10], 1):
            name = source.get("source_name", "Unknown")
            score = source.get("credibility_score", 0)
            lines.append(f"  {i}. {name} ({score:.0f}分)")

        lines.extend([
            "",
            "详细分析:",
            detailed_analysis,
            "",
            "建议:",
        ])

        for rec in recommendations:
            lines.append(f"  - {rec}")

        lines.extend([
            "",
            f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "本报告由 AI 自动生成，仅供参考",
        ])

        return "\n".join(lines)
