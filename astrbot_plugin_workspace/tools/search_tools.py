"""
搜索工具
"""
import fnmatch
import logging
import os
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import WorkspacePlugin

logger = logging.getLogger(__name__)


class SearchTools:
    """搜索工具类"""

    def __init__(self, plugin: "WorkspacePlugin"):
        self.plugin = plugin

    async def search_content(
        self,
        workspace: str,
        keyword: str,
        directory: str = ".",
        file_pattern: str = "*",
        max_results: int = 20,
        context_lines: int = 2
    ) -> str:
        """
        在文件中搜索关键词

        Args:
            workspace: 用户工作区路径
            keyword: 搜索关键词
            directory: 搜索目录（相对于工作区）
            file_pattern: 文件匹配模式
            max_results: 最大结果数
            context_lines: 上下文行数

        Returns:
            搜索结果
        """
        try:
            safe_path = self.plugin.sandbox.resolve_path(directory, workspace)

            if not os.path.exists(safe_path):
                return f"目录不存在: {directory}"

            if not os.path.isdir(safe_path):
                return f"路径不是目录: {directory}"

            # 收集匹配的文件
            files_to_search = []
            for root, dirs, files in os.walk(safe_path):
                for name in files:
                    if fnmatch.fnmatch(name, file_pattern):
                        full_path = os.path.join(root, name)
                        rel_path = os.path.relpath(full_path, workspace)
                        files_to_search.append((rel_path, full_path))

            if not files_to_search:
                return f"没有找到匹配的文件: {file_pattern}"

            # 搜索关键词
            results = []
            total_matches = 0

            for rel_path, full_path in files_to_search:
                if total_matches >= max_results:
                    break

                try:
                    matches = self._search_in_file(
                        full_path, keyword, context_lines
                    )
                    if matches:
                        for match in matches:
                            if total_matches >= max_results:
                                break
                            results.append(f"文件: {rel_path}\n{match}\n")
                            total_matches += 1

                except (OSError, UnicodeDecodeError) as e:
                    # 跳过无法读取的文件（权限问题、编码问题等）
                    logger.debug(f"跳过文件 {rel_path}: {e}")
                    continue

            if not results:
                return f"未找到包含 '{keyword}' 的内容"

            # 汇总结果
            summary = f"找到 {total_matches} 处匹配\n\n"
            summary += "\n---\n".join(results)

            if total_matches >= max_results:
                summary += f"\n\n(结果已截断 最多显示 {max_results} 条)"

            return summary

        except Exception as e:
            return f"搜索失败: {str(e)}"

    def _search_in_file(
        self,
        file_path: str,
        keyword: str,
        context_lines: int = 2
    ) -> list[str]:
        """
        在单个文件中搜索关键词

        Args:
            file_path: 文件路径
            keyword: 搜索关键词
            context_lines: 上下文行数

        Returns:
            匹配结果列表
        """
        results = []

        try:
            with open(file_path, encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            # 编译正则表达式（忽略大小写）
            pattern = re.compile(re.escape(keyword), re.IGNORECASE)

            for i, line in enumerate(lines):
                if pattern.search(line):
                    # 获取上下文
                    start = max(0, i - context_lines)
                    end = min(len(lines), i + context_lines + 1)

                    context = []
                    for j in range(start, end):
                        prefix = ">>> " if j == i else "    "
                        context.append(f"{prefix}行{j + 1}: {lines[j].rstrip()}")

                    results.append("\n".join(context))

        except (OSError, UnicodeDecodeError) as e:
            logger.debug(f"读取文件失败 {file_path}: {e}")

        return results
