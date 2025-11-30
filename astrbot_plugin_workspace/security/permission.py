"""
用户权限管理器
"""


class PermissionManager:
    """用户权限管理器"""

    def __init__(self, config: dict):
        """
        初始化权限管理器

        Args:
            config: 插件配置
        """
        self.enable_whitelist = config.get("enable_whitelist", True)

        # 解析白名单用户
        whitelist_str = config.get("whitelist_users", "")
        self.whitelist_users: set[str] = set(
            u.strip() for u in whitelist_str.split(",") if u.strip()
        )

        # 解析管理员用户
        admin_str = config.get("admin_users", "")
        self.admin_users: set[str] = set(
            u.strip() for u in admin_str.split(",") if u.strip()
        )

    def check_permission(self, user_id: str, user_role: str = "") -> tuple[bool, str]:
        """
        检查用户是否有权限使用插件功能

        Args:
            user_id: 用户ID
            user_role: 用户角色（如 "admin"）

        Returns:
            (是否有权限, 权限级别或错误信息)
        """
        user_id = str(user_id)

        # 管理员始终有权限
        if user_role == "admin" or user_id in self.admin_users:
            return True, "admin"

        # 检查白名单
        if self.enable_whitelist:
            if user_id not in self.whitelist_users:
                return False, "用户不在白名单中，无权使用此功能"

        return True, "member"

    def is_admin(self, user_id: str, user_role: str = "") -> bool:
        """
        检查用户是否为管理员

        Args:
            user_id: 用户ID
            user_role: 用户角色

        Returns:
            是否为管理员
        """
        return user_role == "admin" or str(user_id) in self.admin_users

    def add_to_whitelist(self, user_id: str) -> None:
        """添加用户到白名单"""
        self.whitelist_users.add(str(user_id))

    def remove_from_whitelist(self, user_id: str) -> None:
        """从白名单移除用户"""
        self.whitelist_users.discard(str(user_id))

    def get_whitelist(self) -> set[str]:
        """获取白名单用户列表"""
        return self.whitelist_users.copy()
