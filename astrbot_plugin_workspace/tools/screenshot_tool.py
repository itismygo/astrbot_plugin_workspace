"""
网页截图工具
使用 Playwright 截图，urlscan.io 作为备用方案
"""
import asyncio
import os
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from ..main import WorkspacePlugin

import aiohttp
from astrbot.api import logger


class ScreenshotTool:
    """网页截图工具"""

    def __init__(self, plugin: "WorkspacePlugin"):
        self.plugin = plugin
        self.config = plugin.config.get("screenshot_config", {})
        self.timeout = plugin.config.get("screenshot_timeout", 30)
        self.use_mobile = self.config.get("use_mobile", False)
        self.urlscan_api_key = plugin.config.get("urlscan_api_key", "")

        # User-Agent
        self.pc_user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.mobile_user_agent = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        )

        # Stealth 脚本（绕过反爬检测）
        self.stealth_script = """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['zh-CN', 'zh', 'en']});
        window.chrome = {runtime: {}};
        """

    async def screenshot_page(
        self,
        url: str,
        workspace: str,
        use_mobile: bool = None
    ) -> tuple[str | None, str | None]:
        """
        对网页进行截图

        Args:
            url: 网页 URL
            workspace: 工作区路径
            use_mobile: 是否使用移动端视图

        Returns:
            (screenshot_path, error_message)
        """
        use_mobile = use_mobile if use_mobile is not None else self.use_mobile

        # 优先使用 Playwright
        result = await self._screenshot_with_playwright(url, workspace, use_mobile)
        if result[0]:
            return result

        # Playwright 失败，尝试 urlscan.io 备用方案
        logger.warning(f"Playwright 截图失败，尝试 urlscan.io: {result[1]}")
        return await self._screenshot_with_urlscan(url, workspace)

    async def _screenshot_with_playwright(
        self,
        url: str,
        workspace: str,
        use_mobile: bool = False
    ) -> tuple[str | None, str | None]:
        """使用 Playwright 截图"""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return None, (
                "Playwright 未安装，请运行: "
                "pip install playwright && playwright install chromium"
            )

        screenshot_path = None
        try:
            async with async_playwright() as p:
                # 启动浏览器
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ]
                )

                # 创建上下文
                user_agent = (
                    self.mobile_user_agent if use_mobile else self.pc_user_agent
                )
                viewport = (
                    {"width": 375, "height": 812}
                    if use_mobile
                    else {"width": 1280, "height": 800}
                )
                context_options = {
                    "user_agent": user_agent,
                    "viewport": viewport,
                    "locale": "zh-CN",
                }

                context = await browser.new_context(**context_options)
                page = await context.new_page()

                # 注入 stealth 脚本
                await page.add_init_script(self.stealth_script)

                # 访问页面
                await page.goto(
                    url, wait_until="networkidle", timeout=self.timeout * 1000
                )

                # 等待页面稳定
                await asyncio.sleep(1)

                # 生成截图路径
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_dir = os.path.join(workspace, "outputs", "screenshots")
                os.makedirs(output_dir, exist_ok=True)

                # 从 URL 提取域名作为文件名
                domain = urlparse(url).netloc.replace(".", "_")
                filename = f"screenshot_{domain}_{timestamp}.png"
                screenshot_path = os.path.join(output_dir, filename)

                # 截图
                await page.screenshot(path=screenshot_path, full_page=False)

                await browser.close()

                logger.info(f"Playwright 截图成功: {screenshot_path}")
                return screenshot_path, None

        except Exception as e:
            logger.error(f"Playwright 截图失败: {e}")
            return None, str(e)

    async def _screenshot_with_urlscan(
        self,
        url: str,
        workspace: str
    ) -> tuple[str | None, str | None]:
        """使用 urlscan.io 作为备用截图方案"""
        if not self.urlscan_api_key:
            return None, "urlscan.io API Key 未配置"

        try:
            async with aiohttp.ClientSession() as session:
                # 提交扫描请求
                headers = {
                    "API-Key": self.urlscan_api_key,
                    "Content-Type": "application/json",
                }
                data = {"url": url, "visibility": "unlisted"}

                async with session.post(
                    "https://urlscan.io/api/v1/scan/",
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        return None, (
                            f"urlscan.io 提交失败: {resp.status} - "
                            f"{error_text[:100]}"
                        )
                    result = await resp.json()
                    scan_uuid = result.get("uuid")

                if not scan_uuid:
                    return None, "urlscan.io 未返回扫描 UUID"

                # 等待扫描完成
                logger.info(f"等待 urlscan.io 扫描完成: {scan_uuid}")
                await asyncio.sleep(15)

                # 获取截图
                screenshot_url = f"https://urlscan.io/screenshots/{scan_uuid}.png"
                timeout = aiohttp.ClientTimeout(total=30)
                async with session.get(screenshot_url, timeout=timeout) as resp:
                    if resp.status != 200:
                        return None, f"获取截图失败: {resp.status}"

                    # 保存截图
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_dir = os.path.join(workspace, "outputs", "screenshots")
                    os.makedirs(output_dir, exist_ok=True)
                    filename = f"urlscan_{scan_uuid}_{timestamp}.png"
                    screenshot_path = os.path.join(output_dir, filename)

                    with open(screenshot_path, "wb") as f:
                        f.write(await resp.read())

                    logger.info(f"urlscan.io 截图成功: {screenshot_path}")
                    return screenshot_path, None

        except asyncio.TimeoutError:
            return None, "urlscan.io 请求超时"
        except Exception as e:
            logger.error(f"urlscan.io 截图失败: {e}")
            return None, str(e)

    async def batch_screenshot(
        self,
        urls: list[str],
        workspace: str,
        max_screenshots: int = 5
    ) -> list[dict]:
        """
        批量截图多个 URL

        Args:
            urls: URL 列表
            workspace: 工作区路径
            max_screenshots: 最大截图数量

        Returns:
            截图结果列表 [{"url": url, "path": path, "error": error}, ...]
        """
        results = []
        for url in urls[:max_screenshots]:
            path, error = await self.screenshot_page(url, workspace)
            results.append({
                "url": url,
                "path": path,
                "error": error
            })
        return results

    def get_screenshot_paths(self, workspace: str) -> list[str]:
        """
        获取工作区中所有截图文件路径

        Args:
            workspace: 工作区路径

        Returns:
            截图文件路径列表
        """
        screenshot_dir = os.path.join(workspace, "outputs", "screenshots")
        if not os.path.exists(screenshot_dir):
            return []

        paths = []
        for filename in os.listdir(screenshot_dir):
            if filename.endswith((".png", ".jpg", ".jpeg")):
                paths.append(os.path.join(screenshot_dir, filename))

        return sorted(paths, key=os.path.getmtime, reverse=True)
