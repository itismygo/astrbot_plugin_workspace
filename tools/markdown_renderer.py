"""
Markdown 渲染工具
将 Markdown 文本渲染为图片
"""
import os
import re
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import WorkspacePlugin

from astrbot.api import logger


class MarkdownRenderer:
    """Markdown 渲染器"""

    def __init__(self, plugin: "WorkspacePlugin"):
        self.plugin = plugin
        self.config = plugin.config
        self.max_width = self.config.get("render_max_width", 800)
        self.padding = self.config.get("render_padding", 40)

    async def render_to_image(
        self,
        markdown_text: str,
        workspace: str,
        title: str = ""
    ) -> tuple[str | None, str | None]:
        """
        将 Markdown 渲染为图片

        Args:
            markdown_text: Markdown 文本
            workspace: 工作区路径
            title: 可选标题

        Returns:
            (image_path, error_message)
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return None, "Playwright 未安装，请运行: pip install playwright && playwright install chromium"

        try:
            # 1. 转换 Markdown 为 HTML
            html_content = self._markdown_to_html(markdown_text, title)

            # 2. 使用 Playwright 渲染
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                # 设置页面内容
                await page.set_content(html_content)

                # 等待渲染完成
                await page.wait_for_load_state("networkidle")

                # 获取内容高度
                content_height = await page.evaluate(
                    "document.querySelector('.markdown-body').offsetHeight"
                )

                # 设置视口大小
                await page.set_viewport_size({
                    "width": self.max_width + self.padding * 2,
                    "height": min(content_height + self.padding * 2, 10000)
                })

                # 生成输出路径
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = os.path.join(workspace, "outputs", "renders")
                os.makedirs(output_dir, exist_ok=True)
                image_path = os.path.join(output_dir, f"render_{timestamp}.png")

                # 截图
                await page.screenshot(path=image_path, full_page=True)
                await browser.close()

                logger.info(f"Markdown 渲染成功: {image_path}")
                return image_path, None

        except Exception as e:
            logger.error(f"Markdown 渲染失败: {e}")
            return None, str(e)

    def _markdown_to_html(self, markdown_text: str, title: str = "") -> str:
        """将 Markdown 转换为带样式的 HTML"""
        try:
            import markdown
            html_body = markdown.markdown(
                markdown_text,
                extensions=["tables", "fenced_code", "codehilite", "nl2br"]
            )
        except ImportError:
            # 简单的 Markdown 转换（降级方案）
            html_body = self._simple_markdown_convert(markdown_text)

        title_html = f"<h1 class='title'>{title}</h1>" if title else ""

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            background: #ffffff;
            padding: {self.padding}px;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                         "Helvetica Neue", Arial, "Noto Sans SC", sans-serif;
        }}
        .markdown-body {{
            max-width: {self.max_width}px;
            margin: 0 auto;
            color: #333;
            font-size: 16px;
            line-height: 1.8;
        }}
        .title {{
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #eee;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 24px;
            margin-bottom: 16px;
            font-weight: 600;
            line-height: 1.25;
        }}
        h1 {{ font-size: 2em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
        h2 {{ font-size: 1.5em; border-bottom: 1px solid #eee; padding-bottom: 0.3em; }}
        h3 {{ font-size: 1.25em; }}
        p {{
            margin-bottom: 16px;
        }}
        ul, ol {{
            margin-bottom: 16px;
            padding-left: 2em;
        }}
        li {{
            margin-bottom: 8px;
        }}
        code {{
            background: #f6f8fa;
            padding: 0.2em 0.4em;
            border-radius: 3px;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 85%;
        }}
        pre {{
            background: #f6f8fa;
            padding: 16px;
            border-radius: 6px;
            overflow-x: auto;
            margin-bottom: 16px;
        }}
        pre code {{
            background: none;
            padding: 0;
        }}
        blockquote {{
            border-left: 4px solid #dfe2e5;
            padding-left: 16px;
            color: #6a737d;
            margin-bottom: 16px;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 16px;
        }}
        th, td {{
            border: 1px solid #dfe2e5;
            padding: 8px 12px;
            text-align: left;
        }}
        th {{
            background: #f6f8fa;
            font-weight: 600;
        }}
        tr:nth-child(even) {{
            background: #f9f9f9;
        }}
        a {{
            color: #0366d6;
            text-decoration: none;
        }}
        hr {{
            border: none;
            border-top: 1px solid #eee;
            margin: 24px 0;
        }}
        img {{
            max-width: 100%;
        }}
        .highlight {{
            background: #fffbdd;
            padding: 2px 4px;
        }}
    </style>
</head>
<body>
    <div class="markdown-body">
        {title_html}
        {html_body}
    </div>
</body>
</html>
"""

    def _simple_markdown_convert(self, text: str) -> str:
        """简单的 Markdown 转换（降级方案）"""
        # 标题
        text = re.sub(r"^### (.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
        text = re.sub(r"^## (.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
        text = re.sub(r"^# (.+)$", r"<h1>\1</h1>", text, flags=re.MULTILINE)

        # 粗体和斜体
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)

        # 代码
        text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)

        # 列表
        text = re.sub(r"^- (.+)$", r"<li>\1</li>", text, flags=re.MULTILINE)
        text = re.sub(r"(<li>.*</li>\n?)+", r"<ul>\g<0></ul>", text)

        # 段落
        paragraphs = text.split("\n\n")
        text = "".join(
            f"<p>{p}</p>" if not p.startswith("<") else p
            for p in paragraphs if p.strip()
        )

        return text
