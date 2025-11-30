"""
文本清理工具 - 移除 markdown 格式，保持简洁回复
"""
import re


def clean_markdown(text: str) -> str:
    """
    清理文本中的 markdown 格式

    移除:
    - **粗体** 和 *斜体*
    - `代码` 和 ```代码块```
    - # 标题
    - - 列表项
    - [链接](url)
    - > 引用

    Args:
        text: 原始文本

    Returns:
        清理后的纯文本
    """
    if not text:
        return text

    # 移除代码块 ```...```
    text = re.sub(r'```[\s\S]*?```', lambda m: m.group(0).replace('```', '').strip(), text)

    # 移除行内代码 `code`
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # 移除粗体 **text** 或 __text__
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'__([^_]+)__', r'\1', text)

    # 移除斜体 *text* 或 _text_（注意不要误删单独的下划线）
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'\1', text)
    text = re.sub(r'(?<!_)_([^_\s][^_]*)_(?!_)', r'\1', text)

    # 移除标题 # ## ### 等
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)

    # 移除列表标记 - * + 和数字列表
    text = re.sub(r'^\s*[-*+]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'^\s*\d+\.\s+', '', text, flags=re.MULTILINE)

    # 移除链接 [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)

    # 移除图片 ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)

    # 移除引用 >
    text = re.sub(r'^>\s*', '', text, flags=re.MULTILINE)

    # 移除水平线 --- *** ___
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # 移除多余的空行
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def clean_response(text: str) -> str:
    """
    清理 AI 响应文本，使其更简洁

    除了移除 markdown 外，还会:
    - 移除多余的空白
    - 统一换行符

    Args:
        text: AI 响应文本

    Returns:
        清理后的简洁文本
    """
    if not text:
        return text

    # 先清理 markdown
    text = clean_markdown(text)

    # 移除行首行尾空白
    lines = [line.strip() for line in text.split('\n')]

    # 移除空行但保留段落分隔
    result = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                result.append('')
                prev_empty = True
        else:
            result.append(line)
            prev_empty = False

    return '\n'.join(result).strip()


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """
    截断文本到指定长度

    Args:
        text: 原始文本
        max_length: 最大长度
        suffix: 截断后缀

    Returns:
        截断后的文本
    """
    if not text or len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix
