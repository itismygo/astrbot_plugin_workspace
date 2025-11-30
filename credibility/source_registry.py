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

            # ==================== 技术权威来源 ====================

            # 科技巨头官方博客/文档（最高可信度）
            ("blog.google", "Google官方博客", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("ai.google", "Google AI", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("ai.google.dev", "Google AI开发者", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("deepmind.google", "Google DeepMind", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("developers.google.com", "Google开发者", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("cloud.google.com", "Google Cloud", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("openai.com", "OpenAI官方", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("anthropic.com", "Anthropic官方", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("microsoft.com", "Microsoft官方", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("azure.microsoft.com", "Microsoft Azure", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("devblogs.microsoft.com", "Microsoft开发者博客", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("meta.com", "Meta官方", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("ai.meta.com", "Meta AI", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("engineering.fb.com", "Meta工程博客", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("aws.amazon.com", "AWS官方", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("developer.apple.com", "Apple开发者", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("developer.nvidia.com", "NVIDIA开发者", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),
            ("blogs.nvidia.com", "NVIDIA博客", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "US"),

            # 中国科技公司官方
            ("qwenlm.github.io", "阿里通义千问", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "CN"),
            ("modelscope.cn", "阿里魔搭", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "CN"),
            ("cloud.baidu.com", "百度智能云", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "CN"),
            ("yiyan.baidu.com", "百度文心一言", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "CN"),
            ("open.bigmodel.cn", "智谱AI", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "CN"),
            ("platform.deepseek.com", "DeepSeek官方", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "CN"),
            ("api-docs.deepseek.com", "DeepSeek文档", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "CN"),
            ("hunyuan.tencent.com", "腾讯混元", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "CN"),
            ("cloud.tencent.com", "腾讯云", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "CN"),
            ("minimax.chat", "MiniMax官方", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "CN"),
            ("moonshot.cn", "月之暗面Kimi", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "CN"),
            ("01.ai", "零一万物", CredibilityLevel.HIGHLY_TRUSTED, "tech_official", "CN"),

            # 开源社区/代码托管
            ("github.com", "GitHub", CredibilityLevel.TRUSTED, "tech_platform", "US"),
            ("huggingface.co", "Hugging Face", CredibilityLevel.TRUSTED, "tech_platform", "US"),
            ("arxiv.org", "arXiv论文", CredibilityLevel.HIGHLY_TRUSTED, "academic", "US"),
            ("paperswithcode.com", "Papers With Code", CredibilityLevel.TRUSTED, "academic", "US"),

            # 权威科技媒体
            ("techcrunch.com", "TechCrunch", CredibilityLevel.TRUSTED, "tech_media", "US"),
            ("theverge.com", "The Verge", CredibilityLevel.TRUSTED, "tech_media", "US"),
            ("wired.com", "Wired", CredibilityLevel.TRUSTED, "tech_media", "US"),
            ("arstechnica.com", "Ars Technica", CredibilityLevel.TRUSTED, "tech_media", "US"),
            ("venturebeat.com", "VentureBeat", CredibilityLevel.TRUSTED, "tech_media", "US"),
            ("thenextweb.com", "The Next Web", CredibilityLevel.TRUSTED, "tech_media", "NL"),
            ("zdnet.com", "ZDNet", CredibilityLevel.TRUSTED, "tech_media", "US"),
            ("engadget.com", "Engadget", CredibilityLevel.TRUSTED, "tech_media", "US"),
            ("cnet.com", "CNET", CredibilityLevel.TRUSTED, "tech_media", "US"),
            ("tomshardware.com", "Tom's Hardware", CredibilityLevel.TRUSTED, "tech_media", "US"),
            ("anandtech.com", "AnandTech", CredibilityLevel.TRUSTED, "tech_media", "US"),

            # 中国科技媒体
            ("36kr.com", "36氪", CredibilityLevel.TRUSTED, "tech_media", "CN"),
            ("infoq.cn", "InfoQ中国", CredibilityLevel.TRUSTED, "tech_media", "CN"),
            ("jiqizhixin.com", "机器之心", CredibilityLevel.TRUSTED, "tech_media", "CN"),
            ("leiphone.com", "雷锋网", CredibilityLevel.MODERATE, "tech_media", "CN"),
            ("ithome.com", "IT之家", CredibilityLevel.MODERATE, "tech_media", "CN"),
            ("cnbeta.com.tw", "cnBeta", CredibilityLevel.MODERATE, "tech_media", "CN"),
            ("oschina.net", "开源中国", CredibilityLevel.MODERATE, "tech_media", "CN"),
            ("csdn.net", "CSDN", CredibilityLevel.LOW, "tech_media", "CN"),
            ("juejin.cn", "掘金", CredibilityLevel.LOW, "tech_media", "CN"),
            ("zhihu.com", "知乎", CredibilityLevel.LOW, "social", "CN"),
            ("segmentfault.com", "SegmentFault", CredibilityLevel.LOW, "tech_media", "CN"),

            # AI/ML 专业资源
            ("openreview.net", "OpenReview", CredibilityLevel.HIGHLY_TRUSTED, "academic", "US"),
            ("proceedings.neurips.cc", "NeurIPS", CredibilityLevel.HIGHLY_TRUSTED, "academic", "US"),
            ("proceedings.mlr.press", "ICML/AISTATS", CredibilityLevel.HIGHLY_TRUSTED, "academic", "US"),
            ("aclanthology.org", "ACL Anthology", CredibilityLevel.HIGHLY_TRUSTED, "academic", "US"),
            ("ieeexplore.ieee.org", "IEEE Xplore", CredibilityLevel.HIGHLY_TRUSTED, "academic", "US"),
            ("dl.acm.org", "ACM Digital Library", CredibilityLevel.HIGHLY_TRUSTED, "academic", "US"),

            # AI 评测/排行榜
            ("lmarena.ai", "LMArena", CredibilityLevel.TRUSTED, "tech_benchmark", "US"),
            ("chat.lmsys.org", "LMSYS Chatbot Arena", CredibilityLevel.TRUSTED, "tech_benchmark", "US"),
            ("scale.com", "Scale AI", CredibilityLevel.TRUSTED, "tech_benchmark", "US"),
            ("artificialanalysis.ai", "Artificial Analysis", CredibilityLevel.TRUSTED, "tech_benchmark", "US"),
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
