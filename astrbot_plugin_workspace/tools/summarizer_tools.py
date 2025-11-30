"""
批量总结工具
"""
import fnmatch
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import WorkspacePlugin


class SummarizerTools:
    """批量总结工具类"""

    def __init__(self, plugin: "WorkspacePlugin"):
        self.plugin = plugin

    async def summarize_batch(
        self,
        workspace: str,
        directory: str = ".",
        pattern: str = "*",
        max_files: int = 10,
        max_chars_per_file: int = 2000
    ) -> str:
        """
        批量读取目录中的文件并返回内容摘要

        Args:
            workspace: 用户工作区路径
            directory: 目录路径（相对于工作区）
            pattern: 文件匹配模式
            max_files: 最大处理文件数
            max_chars_per_file: 每个文件最大读取字符数

        Returns:
            文件内容摘要
        """
        try:
            safe_path = self.plugin.sandbox.resolve_path(directory, workspace)

            if not os.path.exists(safe_path):
                return f"目录不存在: {directory}"

            if not os.path.isdir(safe_path):
                return f"路径不是目录: {directory}"

            # 收集匹配的文件
            files = []
            for name in os.listdir(safe_path):
                full_path = os.path.join(safe_path, name)
                if os.path.isfile(full_path) and fnmatch.fnmatch(name, pattern):
                    files.append((name, full_path))

            if not files:
                return f"目录中没有匹配的文件: {directory}"

            # 限制文件数量
            files = files[:max_files]

            # 读取文件信息
            results = []
            for name, full_path in files:
                try:
                    file_size = os.path.getsize(full_path)
                    size_str = self.plugin._format_size(file_size)
                    results.append(f"{name} ({size_str})")
                except Exception:
                    results.append(f"{name} (读取失败)")

            # 简洁格式返回
            return f"共{len(files)}个文件: " + " | ".join(results) + "\n\n回复时只列出文件名和大小 不要解释内容 不要用markdown"

        except Exception as e:
            return f"批量读取失败: {str(e)}"
