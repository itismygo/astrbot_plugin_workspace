"""
Agent 定义模块
"""
from .custom_handoff import ConfigurableAgent, ConfigurableHandoffTool
from .definitions import (
    CODE_ANALYZER_AGENT_INSTRUCTIONS,
    COMMAND_AGENT_INSTRUCTIONS,
    FACT_CHECKER_AGENT_INSTRUCTIONS,
    FILE_AGENT_INSTRUCTIONS,
    ORCHESTRATOR_INSTRUCTIONS,
    SEARCH_AGENT_INSTRUCTIONS,
    SENDER_AGENT_INSTRUCTIONS,
    SUMMARIZER_AGENT_INSTRUCTIONS,
    TASK_PLANNER_AGENT_INSTRUCTIONS,
)
from .orchestrator import (
    create_configurable_handoff_tools,
    create_configurable_sub_agents,
    create_handoff_tools,
    create_orchestrator,
    create_sub_agents,
)
from .parallel_dispatcher import AgentResult, AgentTask, ParallelDispatcher

__all__ = [
    "FILE_AGENT_INSTRUCTIONS",
    "COMMAND_AGENT_INSTRUCTIONS",
    "SENDER_AGENT_INSTRUCTIONS",
    "SUMMARIZER_AGENT_INSTRUCTIONS",
    "SEARCH_AGENT_INSTRUCTIONS",
    "ORCHESTRATOR_INSTRUCTIONS",
    "CODE_ANALYZER_AGENT_INSTRUCTIONS",
    "TASK_PLANNER_AGENT_INSTRUCTIONS",
    "FACT_CHECKER_AGENT_INSTRUCTIONS",
    "create_orchestrator",
    "create_sub_agents",
    "create_handoff_tools",
    "create_configurable_sub_agents",
    "create_configurable_handoff_tools",
    "ConfigurableAgent",
    "ConfigurableHandoffTool",
    "ParallelDispatcher",
    "AgentTask",
    "AgentResult",
]
