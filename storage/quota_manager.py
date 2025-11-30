"""
用户存储配额管理器
"""
import os
import json
import logging
from typing import Tuple, Dict

logger = logging.getLogger(__name__)


class QuotaManager:
    """用户存储配额管理器"""

    def __init__(self, data_dir: str, quota_mb: int = 100):
        """
        初始化配额管理器

        Args:
            data_dir: 数据目录路径
            quota_mb: 每用户配额（MB）
        """
        self.data_dir = data_dir
        self.quota_bytes = quota_mb * 1024 * 1024
        self.quotas_file = os.path.join(data_dir, "config", "quotas.json")

        # 确保配置目录存在
        os.makedirs(os.path.dirname(self.quotas_file), exist_ok=True)

        # 加载配额数据
        self.quotas: Dict[str, dict] = self._load_quotas()

    def _load_quotas(self) -> Dict[str, dict]:
        """加载配额数据"""
        if os.path.exists(self.quotas_file):
            try:
                with open(self.quotas_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (IOError, json.JSONDecodeError, OSError) as e:
                logger.warning(f"加载配额数据失败: {e}")
        return {}

    def _save_quotas(self) -> None:
        """保存配额数据"""
        try:
            with open(self.quotas_file, 'w', encoding='utf-8') as f:
                json.dump(self.quotas, f, indent=2, ensure_ascii=False)
        except (IOError, OSError) as e:
            logger.warning(f"保存配额数据失败: {e}")

    def get_user_usage(self, user_id: str, user_workspace: str) -> int:
        """
        获取用户当前使用的存储空间

        Args:
            user_id: 用户ID
            user_workspace: 用户工作区路径

        Returns:
            使用的字节数
        """
        total_size = 0
        if os.path.exists(user_workspace):
            for dirpath, dirnames, filenames in os.walk(user_workspace):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except (OSError, IOError):
                        # 文件可能被删除或无权限访问，跳过
                        pass
        return total_size

    def check_quota(self, user_id: str, user_workspace: str, additional_bytes: int = 0) -> Tuple[bool, str]:
        """
        检查用户是否有足够的配额

        Args:
            user_id: 用户ID
            user_workspace: 用户工作区路径
            additional_bytes: 额外需要的字节数

        Returns:
            (是否有足够配额, 消息)
        """
        current_usage = self.get_user_usage(user_id, user_workspace)
        total_needed = current_usage + additional_bytes

        if total_needed > self.quota_bytes:
            used_mb = current_usage / 1024 / 1024
            quota_mb = self.quota_bytes / 1024 / 1024
            return False, f"存储配额不足。已使用: {used_mb:.2f}MB / {quota_mb:.0f}MB"

        return True, "OK"

    def get_quota_info(self, user_id: str, user_workspace: str) -> dict:
        """
        获取用户配额信息

        Args:
            user_id: 用户ID
            user_workspace: 用户工作区路径

        Returns:
            配额信息字典
        """
        current_usage = self.get_user_usage(user_id, user_workspace)
        return {
            "used_bytes": current_usage,
            "used_mb": round(current_usage / 1024 / 1024, 2),
            "quota_bytes": self.quota_bytes,
            "quota_mb": round(self.quota_bytes / 1024 / 1024, 0),
            "remaining_bytes": max(0, self.quota_bytes - current_usage),
            "remaining_mb": round(max(0, self.quota_bytes - current_usage) / 1024 / 1024, 2),
            "usage_percent": round(current_usage / self.quota_bytes * 100, 1) if self.quota_bytes > 0 else 0,
        }

    def format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / 1024 / 1024:.2f} MB"
        else:
            return f"{size_bytes / 1024 / 1024 / 1024:.2f} GB"
