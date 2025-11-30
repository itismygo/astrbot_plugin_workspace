"""
路径沙箱管理器 - 确保所有文件操作都在用户专属目录内
"""
import os
import re


class SecurityError(Exception):
    """安全错误"""
    pass


class PathSandbox:
    """路径沙箱管理器"""

    def __init__(self, base_data_dir: str):
        """
        初始化沙箱

        Args:
            base_data_dir: 插件数据目录的基础路径
        """
        self.base_data_dir = base_data_dir
        self.workspaces_dir = os.path.join(base_data_dir, "user_workspaces")
        os.makedirs(self.workspaces_dir, exist_ok=True)

    def _sanitize_user_id(self, user_id: str) -> str:
        """
        清理用户ID，只保留安全字符，防止路径注入

        Args:
            user_id: 原始用户ID

        Returns:
            清理后的安全用户ID
        """
        return re.sub(r"[^a-zA-Z0-9_-]", "_", str(user_id))

    def get_user_workspace(self, user_id: str) -> str:
        """
        获取用户专属工作区目录

        Args:
            user_id: 用户ID

        Returns:
            用户工作区的绝对路径
        """
        safe_user_id = self._sanitize_user_id(user_id)
        user_dir = os.path.join(self.workspaces_dir, safe_user_id)

        # 创建用户目录及子目录
        subdirs = ["documents", "images", "outputs", "temp", "uploads"]
        for subdir in subdirs:
            os.makedirs(os.path.join(user_dir, subdir), exist_ok=True)

        return os.path.abspath(user_dir)

    def validate_path(self, path: str, user_workspace: str) -> tuple[bool, str]:
        """
        验证路径是否在用户工作区内

        Args:
            path: 要验证的路径（相对或绝对）
            user_workspace: 用户工作区路径

        Returns:
            (是否有效, 绝对路径或错误信息)
        """
        try:
            # 解析路径
            if os.path.isabs(path):
                abs_path = os.path.abspath(path)
            else:
                abs_path = os.path.abspath(os.path.join(user_workspace, path))

            # 规范化路径
            abs_path = os.path.normpath(abs_path)
            user_workspace = os.path.normpath(os.path.abspath(user_workspace))

            # 解析符号链接（如果存在）
            if os.path.exists(abs_path):
                real_path = os.path.realpath(abs_path)
            else:
                # 文件不存在时，检查父目录
                parent_dir = os.path.dirname(abs_path)
                if os.path.exists(parent_dir):
                    real_parent = os.path.realpath(parent_dir)
                    real_path = os.path.join(real_parent, os.path.basename(abs_path))
                else:
                    real_path = abs_path

            real_workspace = os.path.realpath(user_workspace)

            # 使用严格的前缀检查，避免 commonpath 边界情况
            # 例如 /workspace 和 /workspace-evil 的 commonpath 是 /workspace
            # 但 /workspace-evil 不应该被允许
            real_path_str = real_path.rstrip(os.sep)
            real_workspace_str = real_workspace.rstrip(os.sep)

            # 检查是否完全匹配或是子目录
            if not (real_path_str == real_workspace_str or
                    real_path_str.startswith(real_workspace_str + os.sep)):
                return False, f"路径超出工作区范围: {path}"

            return True, abs_path

        except Exception as e:
            return False, f"路径验证失败: {str(e)}"

    def resolve_path(self, path: str, user_workspace: str) -> str:
        """
        解析并验证路径，返回安全的绝对路径

        Args:
            path: 要解析的路径
            user_workspace: 用户工作区路径

        Returns:
            安全的绝对路径

        Raises:
            SecurityError: 路径不安全时抛出
        """
        valid, result = self.validate_path(path, user_workspace)
        if not valid:
            raise SecurityError(result)
        return result

    def get_relative_path(self, abs_path: str, user_workspace: str) -> str:
        """
        获取相对于用户工作区的相对路径

        Args:
            abs_path: 绝对路径
            user_workspace: 用户工作区路径

        Returns:
            相对路径
        """
        return os.path.relpath(abs_path, user_workspace)
