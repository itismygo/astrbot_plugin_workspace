"""
定时文件清理器
"""
import asyncio
import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import WorkspacePlugin

logger = logging.getLogger(__name__)


class FileCleaner:
    """定时文件清理器"""

    def __init__(self, plugin: "WorkspacePlugin", config: dict):
        """
        初始化清理器

        Args:
            plugin: 插件实例
            config: 插件配置
        """
        self.plugin = plugin
        self.config = config

        # 清理配置
        self.enable_auto_clean = config.get("enable_auto_clean", True)
        self.clean_interval_hours = config.get("clean_interval_hours", 24)  # 清理间隔（小时）
        self.file_max_age_days = config.get("file_max_age_days", 7)  # 文件最大保留天数
        self.clean_temp_only = config.get("clean_temp_only", False)  # 是否只清理 temp 目录
        self.clean_dirs = config.get("clean_dirs", ["temp", "outputs"])  # 要清理的目录

        # 清理任务
        self._clean_task = None
        self._running = False

    async def start(self):
        """启动定时清理任务"""
        if not self.enable_auto_clean:
            logger.info("自动清理功能已禁用")
            return

        if self._running:
            return

        self._running = True
        self._clean_task = asyncio.create_task(self._clean_loop())
        logger.info(f"定时清理任务已启动，间隔 {self.clean_interval_hours} 小时，保留 {self.file_max_age_days} 天内的文件")

    async def stop(self):
        """停止定时清理任务"""
        self._running = False
        if self._clean_task:
            self._clean_task.cancel()
            try:
                await self._clean_task
            except asyncio.CancelledError:
                pass
            self._clean_task = None
        logger.info("定时清理任务已停止")

    async def _clean_loop(self):
        """清理循环"""
        while self._running:
            try:
                # 等待指定间隔
                await asyncio.sleep(self.clean_interval_hours * 3600)

                if self._running:
                    await self.clean_all_workspaces()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理任务出错: {e}")
                # 出错后等待一段时间再重试
                await asyncio.sleep(3600)

    async def clean_all_workspaces(self):
        """清理所有用户工作区"""
        workspaces_dir = self.plugin.sandbox.workspaces_dir

        if not os.path.exists(workspaces_dir):
            return

        total_cleaned = 0
        total_size = 0

        # 遍历所有用户工作区
        for user_id in os.listdir(workspaces_dir):
            user_workspace = os.path.join(workspaces_dir, user_id)
            if os.path.isdir(user_workspace):
                cleaned, size = await self._clean_workspace(user_workspace, user_id)
                total_cleaned += cleaned
                total_size += size

        if total_cleaned > 0:
            size_str = self._format_size(total_size)
            logger.info(f"定时清理完成: 删除 {total_cleaned} 个文件，释放 {size_str}")

    async def _clean_workspace(self, workspace: str, user_id: str) -> tuple:
        """
        清理单个用户工作区

        Args:
            workspace: 工作区路径
            user_id: 用户ID

        Returns:
            (删除文件数, 释放空间大小)
        """
        cleaned_count = 0
        cleaned_size = 0
        cutoff_time = datetime.now() - timedelta(days=self.file_max_age_days)

        # 确定要清理的目录
        if self.clean_temp_only:
            dirs_to_clean = ["temp"]
        else:
            dirs_to_clean = self.clean_dirs

        for dir_name in dirs_to_clean:
            dir_path = os.path.join(workspace, dir_name)
            if not os.path.exists(dir_path):
                continue

            # 遍历目录中的文件
            for root, dirs, files in os.walk(dir_path, topdown=False):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    try:
                        # 检查文件修改时间
                        mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                        if mtime < cutoff_time:
                            file_size = os.path.getsize(file_path)
                            os.remove(file_path)
                            cleaned_count += 1
                            cleaned_size += file_size
                            logger.debug(f"删除过期文件: {file_path}")
                    except OSError as e:
                        logger.debug(f"删除文件失败 {file_path}: {e}")

                # 删除空目录
                for dirname in dirs:
                    dir_full_path = os.path.join(root, dirname)
                    try:
                        if not os.listdir(dir_full_path):
                            os.rmdir(dir_full_path)
                            logger.debug(f"删除空目录: {dir_full_path}")
                    except OSError:
                        pass

        if cleaned_count > 0:
            logger.info(f"用户 {user_id}: 清理 {cleaned_count} 个文件，释放 {self._format_size(cleaned_size)}")

        return cleaned_count, cleaned_size

    async def clean_user_workspace(self, user_id: str, force: bool = False) -> str:
        """
        手动清理指定用户的工作区

        Args:
            user_id: 用户ID
            force: 是否强制清理所有文件（忽略时间限制）

        Returns:
            清理结果信息
        """
        workspace = self.plugin.sandbox.get_user_workspace(user_id)

        if force:
            # 强制清理：删除 temp 和 outputs 目录中的所有文件
            cleaned_count = 0
            cleaned_size = 0

            for dir_name in ["temp", "outputs"]:
                dir_path = os.path.join(workspace, dir_name)
                if os.path.exists(dir_path):
                    for filename in os.listdir(dir_path):
                        file_path = os.path.join(dir_path, filename)
                        try:
                            if os.path.isfile(file_path):
                                file_size = os.path.getsize(file_path)
                                os.remove(file_path)
                                cleaned_count += 1
                                cleaned_size += file_size
                            elif os.path.isdir(file_path):
                                dir_size = self._get_dir_size(file_path)
                                shutil.rmtree(file_path)
                                cleaned_count += 1
                                cleaned_size += dir_size
                        except OSError as e:
                            logger.warning(f"删除失败 {file_path}: {e}")

            return f"强制清理完成: 删除 {cleaned_count} 个项目，释放 {self._format_size(cleaned_size)}"
        else:
            cleaned, size = await self._clean_workspace(workspace, user_id)
            return f"清理完成: 删除 {cleaned} 个过期文件，释放 {self._format_size(size)}"

    def _get_dir_size(self, path: str) -> int:
        """获取目录大小"""
        total = 0
        for root, dirs, files in os.walk(path):
            for filename in files:
                try:
                    total += os.path.getsize(os.path.join(root, filename))
                except OSError:
                    pass
        return total

    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / 1024 / 1024:.2f} MB"
        else:
            return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"
