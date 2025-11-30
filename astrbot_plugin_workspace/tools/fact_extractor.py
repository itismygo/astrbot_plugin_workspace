"""
可验证事实点提取器
从新闻文本中提取可以被验证的事实声明
"""
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import WorkspacePlugin


@dataclass
class FactPoint:
    """可验证的事实点"""
    statement: str          # 事实陈述
    category: str           # 类别: time/place/person/number/event/quote
    verifiability: str      # 可验证性: high/medium/low
    search_query: str       # 建议的搜索查询
    context: str = ""       # 上下文信息


class FactExtractor:
    """可验证事实点提取器"""

    def __init__(self, plugin: "WorkspacePlugin" = None):
        self.plugin = plugin

        # 事实类别关键词
        self.category_patterns = {
            "time": ["日", "月", "年", "时", "分", "昨天", "今天", "明天", "上周", "本月", "近日", "日前"],
            "place": ["省", "市", "区", "县", "国", "地区", "位于", "在", "当地", "境内"],
            "person": ["人", "官员", "专家", "教授", "医生", "记者", "发言人", "负责人", "主任", "院士"],
            "number": ["万", "亿", "％", "%", "人次", "例", "起", "件", "元", "美元", "吨", "公里"],
            "event": ["发生", "举行", "召开", "发布", "宣布", "通报", "报道", "发现", "确认", "证实"],
            "quote": ["表示", "称", "说", "指出", "强调", "认为", "透露", "介绍", "回应"],
        }

        # 不可验证的主观词汇
        self.subjective_words = [
            "可能", "也许", "大概", "据说", "传闻", "有人说", "听说",
            "我认为", "我觉得", "应该", "必须", "一定", "肯定",
            "震惊", "惊爆", "重磅", "太可怕", "细思极恐", "吓人",
            "据悉", "据了解", "据称", "疑似", "或将", "或许",
        ]

        # 停用词（用于生成搜索查询）
        self.stop_words = [
            "的", "了", "是", "在", "有", "和", "与", "等", "被", "将", "对", "为",
            "这", "那", "个", "些", "着", "过", "到", "从", "向", "把", "给",
        ]

    def extract_facts(self, text: str) -> list[FactPoint]:
        """
        从文本中提取可验证的事实点

        Args:
            text: 新闻文本

        Returns:
            FactPoint 列表
        """
        facts = []

        # 按句子分割
        sentences = self._split_sentences(text)

        for sentence in sentences:
            # 跳过太短的句子
            if len(sentence) < 10:
                continue

            # 检查是否包含主观词汇
            if self._is_subjective(sentence):
                continue

            # 识别事实类别
            category = self._identify_category(sentence)
            if not category:
                continue

            # 评估可验证性
            verifiability = self._assess_verifiability(sentence, category)

            # 生成搜索查询
            search_query = self._generate_search_query(sentence, category)

            facts.append(FactPoint(
                statement=sentence.strip(),
                category=category,
                verifiability=verifiability,
                search_query=search_query
            ))

        # 按可验证性排序，优先返回高可验证性的事实
        facts.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}.get(x.verifiability, 3))

        return facts

    def _split_sentences(self, text: str) -> list[str]:
        """分割句子"""
        # 按中英文句号、问号、感叹号分割
        sentences = re.split(r"[。！？.!?]", text)
        return [s.strip() for s in sentences if s.strip()]

    def _is_subjective(self, sentence: str) -> bool:
        """检查句子是否为主观表达"""
        for word in self.subjective_words:
            if word in sentence:
                return True
        return False

    def _identify_category(self, sentence: str) -> str:
        """识别事实类别"""
        # 按优先级检查类别
        priority_order = ["number", "time", "quote", "event", "place", "person"]

        for category in priority_order:
            patterns = self.category_patterns.get(category, [])
            for pattern in patterns:
                if pattern in sentence:
                    return category
        return ""

    def _assess_verifiability(self, sentence: str, category: str) -> str:
        """评估可验证性"""
        score = 0

        # 包含具体数字
        if re.search(r"\d+", sentence):
            score += 1

        # 包含具体日期
        if re.search(r"\d{4}年|\d{1,2}月|\d{1,2}日", sentence):
            score += 1

        # 包含引用（某人说）
        if any(word in sentence for word in ["表示", "称", "说", "指出"]):
            score += 1

        # 类别加分
        if category in ["time", "number", "quote"]:
            score += 1

        # 包含具体地点
        if re.search(r"[省市区县]|北京|上海|广州|深圳", sentence):
            score += 1

        if score >= 3:
            return "high"
        elif score >= 1:
            return "medium"
        else:
            return "low"

    def _generate_search_query(self, sentence: str, category: str) -> str:
        """生成搜索查询"""
        # 移除停用词
        query = sentence
        for word in self.stop_words:
            query = query.replace(word, " ")

        # 提取数字和日期
        numbers = re.findall(r"\d+[万亿%％元美元人次例起件吨公里]*", sentence)
        dates = re.findall(r"\d{4}年\d{1,2}月\d{1,2}日|\d{1,2}月\d{1,2}日|\d{4}年", sentence)

        # 提取可能的专有名词（连续的中文字符）
        names = re.findall(r"[A-Z][a-z]+|[\u4e00-\u9fa5]{2,4}(?:省|市|区|县|公司|集团|大学|医院)", sentence)

        # 构建查询
        key_parts = []
        if dates:
            key_parts.extend(dates[:1])
        if numbers:
            key_parts.extend(numbers[:2])
        if names:
            key_parts.extend(names[:2])

        # 保留句子的核心部分
        query = re.sub(r"\s+", " ", query).strip()
        if len(query) > 30:
            query = query[:30]

        if key_parts:
            return " ".join(key_parts) + " " + query[:20]
        else:
            return query[:40]

    def filter_verifiable_facts(
        self,
        facts: list[FactPoint],
        min_verifiability: str = "medium"
    ) -> list[FactPoint]:
        """
        过滤出可验证性达标的事实点

        Args:
            facts: 事实点列表
            min_verifiability: 最低可验证性要求

        Returns:
            过滤后的事实点列表
        """
        levels = {"high": 0, "medium": 1, "low": 2}
        min_level = levels.get(min_verifiability, 1)

        return [f for f in facts if levels.get(f.verifiability, 2) <= min_level]

    def generate_verification_plan(self, facts: list[FactPoint]) -> dict:
        """
        生成验证计划

        Args:
            facts: 事实点列表

        Returns:
            验证计划字典
        """
        plan = {
            "total_facts": len(facts),
            "high_priority": [],
            "medium_priority": [],
            "low_priority": [],
            "search_queries": []
        }

        for fact in facts:
            item = {
                "statement": fact.statement,
                "category": fact.category,
                "search_query": fact.search_query
            }

            if fact.verifiability == "high":
                plan["high_priority"].append(item)
            elif fact.verifiability == "medium":
                plan["medium_priority"].append(item)
            else:
                plan["low_priority"].append(item)

            plan["search_queries"].append(fact.search_query)

        return plan

    def format_facts_for_display(self, facts: list[FactPoint]) -> str:
        """
        格式化事实点用于显示

        Args:
            facts: 事实点列表

        Returns:
            格式化的文本
        """
        if not facts:
            return "未能从文本中提取到可验证的事实点。"

        lines = [f"共提取到 {len(facts)} 个可验证事实点：", ""]

        for i, fact in enumerate(facts, 1):
            verifiability_cn = {
                "high": "高",
                "medium": "中",
                "low": "低"
            }.get(fact.verifiability, "未知")

            statement_display = fact.statement[:50] + "..." if len(fact.statement) > 50 else fact.statement

            lines.append(f"{i}. [{verifiability_cn}可验证性] {statement_display}")
            lines.append(f"   类别: {fact.category}")
            lines.append(f"   建议搜索: {fact.search_query}")
            lines.append("")

        # 添加验证建议
        plan = self.generate_verification_plan(facts)
        lines.append(f"验证建议: 优先验证 {len(plan['high_priority'])} 个高可验证性事实点")

        return "\n".join(lines)
