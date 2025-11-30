"""
Agent 定义模块
"""
from .definitions import (
    FILE_AGENT_INSTRUCTIONS,
    COMMAND_AGENT_INSTRUCTIONS,
    SENDER_AGENT_INSTRUCTIONS,
    SUMMARIZER_AGENT_INSTRUCTIONS,
    SEARCH_AGENT_INSTRUCTIONS,
    ORCHESTRATOR_INSTRUCTIONS,
)
from .orchestrator import create_orchestrator, create_sub_agents, create_handoff_tools

__all__ = [
    'FILE_AGENT_INSTRUCTIONS',
    'COMMAND_AGENT_INSTRUCTIONS',
    'SENDER_AGENT_INSTRUCTIONS',
    'SUMMARIZER_AGENT_INSTRUCTIONS',
    'SEARCH_AGENT_INSTRUCTIONS',
    'ORCHESTRATOR_INSTRUCTIONS',
    'create_orchestrator',
    'create_sub_agents',
    'create_handoff_tools',
]
