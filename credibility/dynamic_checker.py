"""
动态可信度评估器
检查域名年龄、HTTPS、备案等动态指标
"""
import asyncio
import re
from dataclasses import dataclass

import aiohttp
from astrbot.api import logger


@dataclass
class DynamicCheckResult:
    """动态检查结果"""
    domain: str
    has_https: bool = False
    ssl_valid: bool = False
    ssl_issuer: str = ""
    domain_age_days: int = -1
    has_icp: bool = False
    icp_number: str = ""
    score_adjustment: int = 0


class DynamicChecker:
    """动态可信度检查器"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.timeout = self.config.get("timeout", 10)

    async def check_all(self, url: str) -> DynamicCheckResult:
        """执行所有动态检查"""
        domain = self._extract_domain(url)
        result = DynamicCheckResult(domain=domain)

        # 并行执行所有检查
        checks = await asyncio.gather(
            self._check_https(url),
            self._check_domain_age(domain),
            self._check_icp(domain),
            return_exceptions=True
        )

        # 处理 HTTPS 检查结果
        if isinstance(checks[0], dict):
            result.has_https = checks[0].get("has_https", False)
            result.ssl_valid = checks[0].get("ssl_valid", False)
            result.ssl_issuer = checks[0].get("ssl_issuer", "")

        # 处理域名年龄检查结果
        if isinstance(checks[1], int):
            result.domain_age_days = checks[1]

        # 处理 ICP 备案检查结果
        if isinstance(checks[2], dict):
            result.has_icp = checks[2].get("has_icp", False)
            result.icp_number = checks[2].get("icp_number", "")

        # 计算评分调整值
        result.score_adjustment = self._calculate_adjustment(result)
        return result

    async def _check_https(self, url: str) -> dict:
        """检查 HTTPS 和 SSL 证书"""
        result = {"has_https": False, "ssl_valid": False, "ssl_issuer": ""}

        # 确保使用 HTTPS
        if url.startswith("http://"):
            https_url = url.replace("http://", "https://")
        elif url.startswith("https://"):
            https_url = url
        else:
            https_url = f"https://{url}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    https_url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                    ssl=True,
                    allow_redirects=True
                ):
                    result["has_https"] = True
                    result["ssl_valid"] = True
                    # 注意：aiohttp 不直接暴露 SSL 证书信息
                    # 如需获取证书详情，需要使用 ssl 模块
        except aiohttp.ClientSSLError:
            result["has_https"] = True
            result["ssl_valid"] = False
        except Exception as e:
            logger.debug(f"HTTPS 检查失败: {e}")

        return result

    async def _check_domain_age(self, domain: str) -> int:
        """
        检查域名年龄（通过 WHOIS API）

        注意：这里返回 -1 表示无法获取
        实际使用时可以接入 WHOIS API 服务
        """
        # 可以调用 WHOIS API 服务，如：
        # - whoisxmlapi.com
        # - jsonwhois.com
        # 由于需要 API Key，这里返回默认值
        return -1

    async def _check_icp(self, domain: str) -> dict:
        """
        检查中国 ICP 备案

        注意：实际使用时可以接入备案查询 API
        """
        result = {"has_icp": False, "icp_number": ""}

        # 可以调用备案查询 API，如：
        # - 工信部备案查询
        # - 第三方备案查询服务
        # 由于需要 API 或爬虫，这里返回默认值

        return result

    def _calculate_adjustment(self, result: DynamicCheckResult) -> int:
        """计算评分调整值"""
        adjustment = 0

        # HTTPS 和有效 SSL 证书加分
        if result.has_https and result.ssl_valid:
            adjustment += 5
        elif result.has_https:
            adjustment += 2

        # 域名年龄加分
        if result.domain_age_days > 730:  # 超过2年
            adjustment += 10
        elif result.domain_age_days > 365:  # 超过1年
            adjustment += 5
        elif result.domain_age_days > 0 and result.domain_age_days < 90:  # 新域名减分
            adjustment -= 5

        # ICP 备案加分（中国网站）
        if result.has_icp:
            adjustment += 5

        return adjustment

    def _extract_domain(self, url: str) -> str:
        """从URL提取域名"""
        pattern = r"https?://(?:www\.)?([^/]+)"
        match = re.search(pattern, url)
        return match.group(1) if match else url

    async def quick_check(self, url: str) -> dict:
        """快速检查（仅检查 HTTPS）"""
        https_result = await self._check_https(url)
        return {
            "url": url,
            "has_https": https_result.get("has_https", False),
            "ssl_valid": https_result.get("ssl_valid", False),
        }
