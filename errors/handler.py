"""
错误处理器 - 错误分类、重试机制、用户友好消息
"""

# 用户友好的错误消息（简洁无技术细节）
ERROR_MESSAGES = {
    "FileNotFoundError": "文件不存在 请检查路径",
    "PermissionError": "没有权限执行此操作",
    "QuotaExceededError": "存储空间不足 请清理一些文件",
    "SecurityError": "路径不在允许范围内",
    "InvalidCommandError": "不支持此命令",
    "TimeoutError": "操作超时 请稍后重试",
    "asyncio.TimeoutError": "操作超时 请稍后重试",
    "ProcessError": "处理失败 请稍后重试",
    "IOError": "读写失败 请稍后重试",
    "OSError": "系统错误 请稍后重试",
    "default": "操作失败 请稍后重试",
}

# 不可恢复错误 - 不重试
UNRECOVERABLE_ERRORS = [
    "FileNotFoundError",
    "PermissionError",
    "QuotaExceededError",
    "SecurityError",
    "InvalidCommandError",
    "FileExistsError",
    "IsADirectoryError",
    "NotADirectoryError",
]

# 可恢复错误 - 可重试
RECOVERABLE_ERRORS = [
    "TimeoutError",
    "asyncio.TimeoutError",
    "ProcessError",
    "IOError",
    "OSError",
    "ConnectionError",
    "TemporaryIOError",
]

# 重试配置
RETRY_CONFIG = {
    "max_retries": 2,           # 默认最大重试次数
    "timeout_retries": 1,       # 超时错误最多重试1次
    "io_retries": 2,            # IO错误最多重试2次
}


class ErrorHandler:
    """错误处理器"""

    def __init__(self):
        self.retry_counts = {}  # task_id -> retry_count

    def should_retry(
        self,
        error: Exception,
        task_id: str,
        max_retries: int = None
    ) -> tuple[bool, str | None]:
        """
        判断是否应该重试

        Args:
            error: 异常对象
            task_id: 任务标识（用于跟踪重试次数）
            max_retries: 最大重试次数，None 使用默认值

        Returns:
            (是否重试, 错误消息或None)
        """
        error_type = type(error).__name__

        # 不可恢复错误 - 不重试
        if error_type in UNRECOVERABLE_ERRORS:
            return False, self.get_user_message(error)

        # 确定最大重试次数
        if max_retries is None:
            if "Timeout" in error_type:
                max_retries = RETRY_CONFIG["timeout_retries"]
            elif error_type in ["IOError", "OSError"]:
                max_retries = RETRY_CONFIG["io_retries"]
            else:
                max_retries = RETRY_CONFIG["max_retries"]

        # 检查重试次数
        current_retries = self.retry_counts.get(task_id, 0)
        if current_retries >= max_retries:
            return False, self.get_user_message(error)

        # 可以重试
        self.retry_counts[task_id] = current_retries + 1
        return True, None

    def get_user_message(self, error: Exception) -> str:
        """
        获取用户友好的错误消息

        Args:
            error: 异常对象

        Returns:
            简洁的错误消息
        """
        error_type = type(error).__name__
        return ERROR_MESSAGES.get(error_type, ERROR_MESSAGES["default"])

    def reset_retry_count(self, task_id: str):
        """重置任务的重试计数"""
        self.retry_counts.pop(task_id, None)

    def clear_all(self):
        """清除所有重试计数"""
        self.retry_counts.clear()

    def is_unrecoverable(self, error: Exception) -> bool:
        """判断是否为不可恢复错误"""
        return type(error).__name__ in UNRECOVERABLE_ERRORS

    def classify_error(self, error: Exception) -> str:
        """
        分类错误类型

        Returns:
            "unrecoverable" | "recoverable" | "unknown"
        """
        error_type = type(error).__name__
        if error_type in UNRECOVERABLE_ERRORS:
            return "unrecoverable"
        elif error_type in RECOVERABLE_ERRORS:
            return "recoverable"
        else:
            return "unknown"
