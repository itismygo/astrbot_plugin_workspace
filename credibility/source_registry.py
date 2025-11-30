"""
来源注册表
管理媒体白名单和黑名单
"""
import re
from dataclasses import dataclass, field
from enum import Enum


class CredibilityLevel(Enum):
    """可信度等级"""
    HIGHLY_TRUSTED = 5      # 高度可信（权威官方媒体）
    TRUSTED = 4             # 可信（主流媒体）
    MODERATE = 3            # 中等（一般媒体）
    LOW = 2                 # 低可信度（需谨慎）
    UNTRUSTED = 1           # 不可信（已知假新闻源）
    UNKNOWN = 0             # 未知来源


@dataclass
class SourceCredibility:
    """来源可信度信息"""
    domain: str
    name: str
    level: CredibilityLevel
    category: str  # official, mainstream, regional, social, factcheck, unknown
    country: str = ""
    notes: str = ""


@dataclass
class SourceRegistry:
    """来源注册表"""
    whitelist: dict[str, SourceCredibility] = field(default_factory=dict)
    blacklist: dict[str, SourceCredibility] = field(default_factory=dict)
    custom_rules: list[dict] = field(default_factory=list)

    def __post_init__(self):
        self._init_default_whitelist()
        self._init_default_blacklist()

    def _init_default_whitelist(self):
        """初始化默认白名单"""
        trusted_sources = [
            # 中国官方媒体
            ("xinhuanet.com", "新华社", CredibilityLevel.HIGHLY_TRUSTED, "official", "CN"),
            ("people.com.cn", "人民日报", CredibilityLevel.HIGHLY_TRUSTED, "official", "CN"),
            ("cctv.com", "央视网", CredibilityLevel.HIGHLY_TRUSTED, "official", "CN"),
            ("gov.cn", "中国政府网", CredibilityLevel.HIGHLY_TRUSTED, "official", "CN"),
            ("chinanews.com.cn", "中国新闻网", CredibilityLevel.TRUSTED, "official", "CN"),
            ("gmw.cn", "光明网", CredibilityLevel.TRUSTED, "official", "CN"),
            ("youth.cn", "中国青年网", CredibilityLevel.TRUSTED, "official", "CN"),
            ("china.com.cn", "中国网", CredibilityLevel.TRUSTED, "official", "CN"),

            # 国际权威媒体
            ("reuters.com", "Reuters", CredibilityLevel.HIGHLY_TRUSTED, "mainstream", "UK"),
            ("apnews.com", "AP News", CredibilityLevel.HIGHLY_TRUSTED, "mainstream", "US"),
            ("bbc.com", "BBC", CredibilityLevel.TRUSTED, "mainstream", "UK"),
            ("bbc.co.uk", "BBC", CredibilityLevel.TRUSTED, "mainstream", "UK"),
            ("cnn.com", "CNN", CredibilityLevel.TRUSTED, "mainstream", "US"),
            ("nytimes.com", "New York Times", CredibilityLevel.TRUSTED, "mainstream", "US"),
            ("washingtonpost.com", "Washington Post", CredibilityLevel.TRUSTED, "mainstream", "US"),
            ("theguardian.com", "The Guardian", CredibilityLevel.TRUSTED, "mainstream", "UK"),
            ("wsj.com", "Wall Street Journal", CredibilityLevel.TRUSTED, "mainstream", "US"),
            ("ft.com", "Financial Times", CredibilityLevel.TRUSTED, "mainstream", "UK"),
            ("economist.com", "The Economist", CredibilityLevel.TRUSTED, "mainstream", "UK"),

            # 事实核查机构
            ("snopes.com", "Snopes", CredibilityLevel.TRUSTED, "factcheck", "US"),
            ("factcheck.org", "FactCheck.org", CredibilityLevel.TRUSTED, "factcheck", "US"),
            ("politifact.com", "PolitiFact", CredibilityLevel.TRUSTED, "factcheck", "US"),
            ("fullfact.org", "Full Fact", CredibilityLevel.TRUSTED, "factcheck", "UK"),

            # 学术/专业/国际组织
            ("nature.com", "Nature", CredibilityLevel.HIGHLY_TRUSTED, "academic", "UK"),
            ("science.org", "Science", CredibilityLevel.HIGHLY_TRUSTED, "academic", "US"),
            ("who.int", "WHO", CredibilityLevel.HIGHLY_TRUSTED, "official", "INT"),
            ("un.org", "United Nations", CredibilityLevel.HIGHLY_TRUSTED, "official", "INT"),
            ("worldbank.org", "World Bank", CredibilityLevel.HIGHLY_TRUSTED, "official", "INT"),

            # 中国主流门户（新闻频道）
            ("news.sina.com.cn", "新浪新闻", CredibilityLevel.MODERATE, "mainstream", "CN"),
            ("news.163.com", "网易新闻", CredibilityLevel.MODERATE, "mainstream", "CN"),
            ("news.qq.com", "腾讯新闻", CredibilityLevel.MODERATE, "mainstream", "CN"),
            ("news.sohu.com", "搜狐新闻", CredibilityLevel.MODERATE, "mainstream", "CN"),
            ("thepaper.cn", "澎湃新闻", CredibilityLevel.TRUSTED, "mainstream", "CN"),
            ("caixin.com", "财新网", CredibilityLevel.TRUSTED, "mainstream", "CN"),
        ]

        for domain, name, level, category, country in trusted_sources:
            self.whitelist[domain] = SourceCredibility(
                domain=domain, name=name, level=level,
                category=category, country=country
            )

    def _init_default_blacklist(self):
        """初始化默认黑名单（已知假新闻源）"""
        untrusted_sources = [
            # 已知的假新闻/低质量来源（示例）
            # 实际使用时可从配置文件加载
        ]

        for domain, name, level, category, country in untrusted_sources:
            self.blacklist[domain] = SourceCredibility(
                domain=domain, name=name, level=level,
                category=category, country=country
            )

    def get_credibility(self, url: str) -> SourceCredibility:
        """获取URL的可信度信息"""
        domain = self._extract_domain(url)

        # 先检查白名单
        for key in self.whitelist:
            if key in domain:
                return self.whitelist[key]

        # 再检查黑名单
        for key in self.blacklist:
            if key in domain:
                return self.blacklist[key]

        # 未知来源
        return SourceCredibility(
            domain=domain, name="Unknown",
            level=CredibilityLevel.UNKNOWN, category="unknown"
        )

    def _extract_domain(self, url: str) -> str:
        """从URL提取域名"""
        pattern = r"https?://(?:www\.)?([^/]+)"
        match = re.search(pattern, url)
        return match.group(1) if match else url

    def add_custom_source(self, domain: str, name: str, level: CredibilityLevel, category: str):
        """添加自定义来源到白名单"""
        self.whitelist[domain] = SourceCredibility(
            domain=domain, name=name, level=level, category=category
        )

    def add_to_blacklist(self, domain: str, name: str, notes: str = ""):
        """添加来源到黑名单"""
        self.blacklist[domain] = SourceCredibility(
            domain=domain, name=name,
            level=CredibilityLevel.UNTRUSTED,
            category="blacklisted",
            notes=notes
        )

    def is_trusted(self, url: str) -> bool:
        """检查URL是否来自可信来源"""
        credibility = self.get_credibility(url)
        return credibility.level.value >= CredibilityLevel.TRUSTED.value

    def is_untrusted(self, url: str) -> bool:
        """检查URL是否来自不可信来源"""
        credibility = self.get_credibility(url)
        return credibility.level.value <= CredibilityLevel.UNTRUSTED.value
