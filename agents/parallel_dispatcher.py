"""
并行 Agent 调度器
支持同时派发多个子 Agent 执行任务
"""
import asyncio
from dataclasses import dataclass
from typing import Any

from astrbot.api import logger


@dataclass
class AgentTask:
    """Agent 任务定义"""
    agent_name: str
    task_input: str


@dataclass
class AgentResult:
    """Agent 执行结果"""
    agent_name: str
    success: bool
    result: str
    error: str | None = None


class ParallelDispatcher:
    """并行 Agent 调度器"""

    def __init__(self, plugin_instance):
        """
        初始化调度器

        Args:
            plugin_instance: WorkspacePlugin 实例，用于访问工具和配置
        """
        self.plugin = plugin_instance
        self.max_parallel = 5  # 最大并行数

    async def dispatch(
        self,
        event,
        tasks: list[AgentTask],
        timeout: int = 120
    ) -> list[AgentResult]:
        """
        并行派发多个 Agent 任务

        Args:
            event: AstrMessageEvent
            tasks: Agent 任务列表
            timeout: 超时时间（秒）

        Returns:
            AgentResult 列表
        """
        if len(tasks) > self.max_parallel:
            tasks = tasks[:self.max_parallel]
            logger.warning(f"任务数超过限制，截取前 {self.max_parallel} 个")

        # 创建并行任务
        coroutines = [
            self._execute_agent_task(event, task, timeout)
            for task in tasks
        ]

        # 并行执行
        results = await asyncio.gather(*coroutines, return_exceptions=True)

        # 处理结果
        agent_results = []
        for task, result in zip(tasks, results):
            if isinstance(result, Exception):
                agent_results.append(AgentResult(
                    agent_name=task.agent_name,
                    success=False,
                    result="",
                    error=str(result)
                ))
            else:
                agent_results.append(result)

        return agent_results

    async def _execute_agent_task(
        self,
        event,
        task: AgentTask,
        timeout: int
    ) -> AgentResult:
        """
        执行单个 Agent 任务

        这里使用 context.tool_loop_agent 来运行子 Agent
        """
        try:
            # 获取 Agent 配置
            agent_config = self._get_agent_config(task.agent_name)
            if not agent_config:
                return AgentResult(
                    agent_name=task.agent_name,
                    success=False,
                    result="",
                    error=f"未找到 Agent: {task.agent_name}"
                )

            # 获取模型提供商 ID
            provider_id = agent_config.get("provider_id")
            if not provider_id:
                umo = event.unified_msg_origin
                provider_id = await self.plugin.context.get_current_chat_provider_id(umo=umo)

            # 构建工具集
            tools = self._build_toolset(agent_config.get("tools", []))

            # 调用 Agent
            llm_resp = await asyncio.wait_for(
                self.plugin.context.tool_loop_agent(
                    event=event,
                    chat_provider_id=provider_id,
                    prompt=task.task_input,
                    system_prompt=agent_config.get("instructions", ""),
                    tools=tools,
                    max_steps=agent_config.get("max_steps", 15),
                ),
                timeout=timeout
            )

            return AgentResult(
                agent_name=task.agent_name,
                success=True,
                result=llm_resp.completion_text or ""
            )

        except asyncio.TimeoutError:
            return AgentResult(
                agent_name=task.agent_name,
                success=False,
                result="",
                error=f"执行超时 ({timeout}秒)"
            )
        except Exception as e:
            logger.error(f"Agent {task.agent_name} 执行失败: {e}")
            return AgentResult(
                agent_name=task.agent_name,
                success=False,
                result="",
                error=str(e)
            )

    def _get_agent_config(self, agent_name: str) -> dict[str, Any] | None:
        """获取 Agent 配置"""
        from .definitions import (
            CODE_ANALYZER_AGENT_INSTRUCTIONS,
            FACT_CHECKER_AGENT_INSTRUCTIONS,
            FILE_AGENT_INSTRUCTIONS,
            SEARCH_AGENT_INSTRUCTIONS,
            SUMMARIZER_AGENT_INSTRUCTIONS,
            TASK_PLANNER_AGENT_INSTRUCTIONS,
        )

        # Agent 配置映射
        agent_configs = {
            "code_analyzer_agent": {
                "instructions": CODE_ANALYZER_AGENT_INSTRUCTIONS,
                "tools": ["read_file", "list_files", "search_content"],
                "provider_id": self.plugin.code_analyzer_provider_id or None,
                "max_steps": 20,
            },
            "task_planner_agent": {
                "instructions": TASK_PLANNER_AGENT_INSTRUCTIONS,
                "tools": ["read_file", "list_files", "write_file"],
                "provider_id": self.plugin.task_planner_provider_id or None,
                "max_steps": 15,
            },
            "file_agent": {
                "instructions": FILE_AGENT_INSTRUCTIONS,
                "tools": ["read_file", "write_file", "edit_file", "list_files", "rename_file", "delete_file"],
                "provider_id": None,
                "max_steps": 20,
            },
            "search_agent": {
                "instructions": SEARCH_AGENT_INSTRUCTIONS,
                "tools": ["list_files", "read_file", "search_content"],
                "provider_id": None,
                "max_steps": 15,
            },
            "summarizer_agent": {
                "instructions": SUMMARIZER_AGENT_INSTRUCTIONS,
                "tools": ["read_file", "list_files", "summarize_batch"],
                "provider_id": None,
                "max_steps": 15,
            },
            "fact_checker_agent": {
                "instructions": FACT_CHECKER_AGENT_INSTRUCTIONS,
                "tools": [
                    "extract_facts", "evaluate_sources", "analyze_results",
                    "generate_report", "verify_news",
                    "read_file", "write_file", "list_files"
                ],
                "provider_id": getattr(self.plugin, "fact_checker_provider_id", None),
                "max_steps": 25,
            },
        }

        return agent_configs.get(agent_name)

    def _build_toolset(self, tool_names: list[str]):
        """构建工具集"""
        from astrbot.core.agent.tool import ToolSet
        from astrbot.core.provider.register import llm_tools as tool_manager

        tools = []
        for name in tool_names:
            tool = tool_manager.get_func(name)
            if tool:
                tools.append(tool)

        return ToolSet(tools=tools) if tools else None

    def format_results(self, results: list[AgentResult]) -> str:
        """格式化并行执行结果"""
        output_parts = []

        for result in results:
            if result.success:
                output_parts.append(f"[{result.agent_name}]\n{result.result}")
            else:
                output_parts.append(f"[{result.agent_name}] 失败: {result.error}")

        return "\n\n---\n\n".join(output_parts)
