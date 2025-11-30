"""
Orchestrator 钩子 - 信息过滤和错误处理
"""
from typing import TYPE_CHECKING, Optional, Any

from mcp.types import CallToolResult

from astrbot.core.agent.hooks import BaseAgentRunHooks
from astrbot.core.agent.run_context import ContextWrapper
from astrbot.core.astr_agent_context import AstrAgentContext
from astrbot.core.provider.entities import LLMResponse
from astrbot.core.agent.tool import FunctionTool

from ..utils.text_cleaner import clean_response
from ..errors.handler import ErrorHandler

if TYPE_CHECKING:
    from ..main import WorkspacePlugin


class OrchestratorHooks(BaseAgentRunHooks[AstrAgentContext]):
    """
    Orchestrator Agent 的钩子

    功能:
    1. 过滤子 Agent 的中间输出
    2. 清理最终响应中的 markdown 格式
    3. 处理错误并简化错误消息
    """

    def __init__(self, plugin: "WorkspacePlugin"):
        """
        初始化钩子

        Args:
            plugin: 插件实例
        """
        self.plugin = plugin
        self.error_handler = ErrorHandler()
        self.in_sub_agent = False
        self.sub_agent_results = []
        self.current_task_id = None

    async def on_agent_begin(self, run_context: ContextWrapper[AstrAgentContext]):
        """Agent 开始执行时调用"""
        self.sub_agent_results = []
        self.in_sub_agent = False
        # 生成任务 ID 用于错误重试跟踪
        import uuid
        self.current_task_id = str(uuid.uuid4())[:8]

    async def on_tool_start(
        self,
        run_context: ContextWrapper[AstrAgentContext],
        tool: FunctionTool[Any],
        tool_args: dict | None,
    ):
        """工具调用前调用"""
        # 检测是否进入子 Agent
        if hasattr(tool, 'name') and tool.name.startswith("transfer_to_"):
            self.in_sub_agent = True
            # 可以在这里阻止中间消息发送
            # 但 AstrBot 的实现可能不支持直接阻止

    async def on_tool_end(
        self,
        run_context: ContextWrapper[AstrAgentContext],
        tool: FunctionTool[Any],
        tool_args: dict | None,
        tool_result: CallToolResult | None,
    ):
        """工具调用后调用"""
        if hasattr(tool, 'name') and tool.name.startswith("transfer_to_"):
            self.in_sub_agent = False
            # 收集子 Agent 结果
            if tool_result:
                agent_name = tool.name.replace("transfer_to_", "")
                self.sub_agent_results.append({
                    "agent": agent_name,
                    "result": tool_result,
                    "args": tool_args,
                })

    async def on_agent_done(
        self,
        run_context: ContextWrapper[AstrAgentContext],
        llm_response: LLMResponse,
    ):
        """Agent 完成时调用"""
        # 清理最终响应中的 markdown 格式
        if llm_response and llm_response.completion_text:
            llm_response.completion_text = clean_response(
                llm_response.completion_text
            )

        # 重置错误处理器的重试计数
        if self.current_task_id:
            self.error_handler.reset_retry_count(self.current_task_id)

    def should_retry_error(self, error: Exception) -> tuple:
        """
        判断是否应该重试错误

        Args:
            error: 异常对象

        Returns:
            (是否重试, 用户友好的错误消息或None)
        """
        return self.error_handler.should_retry(
            error,
            self.current_task_id or "default"
        )

    def get_error_message(self, error: Exception) -> str:
        """获取用户友好的错误消息"""
        return self.error_handler.get_user_message(error)
