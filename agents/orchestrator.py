"""
Orchestrator Agent 创建和配置
"""
from typing import TYPE_CHECKING

from astrbot.core.agent.agent import Agent
from astrbot.core.agent.handoff import HandoffTool

from .custom_handoff import ConfigurableAgent, ConfigurableHandoffTool
from .definitions import (
    CODE_ANALYZER_AGENT_INSTRUCTIONS,
    COMMAND_AGENT_INSTRUCTIONS,
    FILE_AGENT_INSTRUCTIONS,
    ORCHESTRATOR_INSTRUCTIONS,
    SEARCH_AGENT_INSTRUCTIONS,
    SENDER_AGENT_INSTRUCTIONS,
    SUMMARIZER_AGENT_INSTRUCTIONS,
    TASK_PLANNER_AGENT_INSTRUCTIONS,
)

if TYPE_CHECKING:
    from ..hooks.orchestrator_hooks import OrchestratorHooks


def create_sub_agents() -> dict:
    """
    创建所有子 Agent

    Returns:
        Agent 名称到 Agent 对象的映射
    """
    file_agent = Agent(
        name="file_agent",
        instructions=FILE_AGENT_INSTRUCTIONS,
        tools=["read_file", "write_file", "edit_file", "list_files", "rename_file", "delete_file"],
    )

    command_agent = Agent(
        name="command_agent",
        instructions=COMMAND_AGENT_INSTRUCTIONS,
        tools=["execute_command", "convert_pdf"],
    )

    sender_agent = Agent(
        name="sender_agent",
        instructions=SENDER_AGENT_INSTRUCTIONS,
        tools=["send_file"],
    )

    summarizer_agent = Agent(
        name="summarizer_agent",
        instructions=SUMMARIZER_AGENT_INSTRUCTIONS,
        tools=["read_file", "list_files", "summarize_batch"],
    )

    search_agent = Agent(
        name="search_agent",
        instructions=SEARCH_AGENT_INSTRUCTIONS,
        tools=["list_files", "read_file", "search_content"],
    )

    return {
        "file_agent": file_agent,
        "command_agent": command_agent,
        "sender_agent": sender_agent,
        "summarizer_agent": summarizer_agent,
        "search_agent": search_agent,
    }


def create_handoff_tools(sub_agents: dict = None) -> list[HandoffTool]:
    """
    为所有子 Agent 创建 HandoffTool

    Args:
        sub_agents: 子 Agent 字典，如果为 None 则自动创建

    Returns:
        HandoffTool 列表
    """
    if sub_agents is None:
        sub_agents = create_sub_agents()

    handoff_tools = []
    for agent in sub_agents.values():
        handoff_tools.append(HandoffTool(agent))

    return handoff_tools


def create_orchestrator(
    hooks: "OrchestratorHooks" = None,
    sub_agents: dict = None
) -> Agent:
    """
    创建中枢 Orchestrator Agent

    Args:
        hooks: Orchestrator 钩子（用于信息过滤和错误处理）
        sub_agents: 子 Agent 字典，如果为 None 则自动创建

    Returns:
        Orchestrator Agent 对象
    """
    if sub_agents is None:
        sub_agents = create_sub_agents()

    # 创建 HandoffTools
    handoff_tools = create_handoff_tools(sub_agents)

    # Orchestrator 的工具列表：HandoffTools + 直接工具
    tools = handoff_tools + ["get_workspace_info"]

    return Agent(
        name="orchestrator",
        instructions=ORCHESTRATOR_INSTRUCTIONS,
        tools=tools,
        run_hooks=hooks,
    )


def create_configurable_sub_agents(config: dict = None) -> dict:
    """
    创建可配置的子 Agent（支持指定模型提供商）

    Args:
        config: 插件配置，包含代理开关和模型提供商设置

    Returns:
        Agent 名称到 ConfigurableAgent 对象的映射
    """
    config = config or {}
    agents = {}

    # 代码分析代理
    if config.get("enable_code_analyzer", True):
        code_analyzer_agent = ConfigurableAgent(
            name="code_analyzer_agent",
            instructions=CODE_ANALYZER_AGENT_INSTRUCTIONS,
            tools=["read_file", "list_files", "search_content"],
            provider_id=config.get("code_analyzer_provider_id") or None,
            max_steps=20,
        )
        agents["code_analyzer_agent"] = code_analyzer_agent

    # 任务规划代理
    if config.get("enable_task_planner", True):
        task_planner_agent = ConfigurableAgent(
            name="task_planner_agent",
            instructions=TASK_PLANNER_AGENT_INSTRUCTIONS,
            tools=["read_file", "list_files", "write_file"],
            provider_id=config.get("task_planner_provider_id") or None,
            max_steps=15,
        )
        agents["task_planner_agent"] = task_planner_agent

    return agents


def create_configurable_handoff_tools(agents: dict) -> list[ConfigurableHandoffTool]:
    """
    为 ConfigurableAgent 创建 HandoffTool

    Args:
        agents: ConfigurableAgent 字典

    Returns:
        ConfigurableHandoffTool 列表
    """
    handoff_tools = []
    for agent in agents.values():
        if isinstance(agent, ConfigurableAgent):
            handoff_tools.append(ConfigurableHandoffTool(agent))
    return handoff_tools
