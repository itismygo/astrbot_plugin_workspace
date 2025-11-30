"""
自定义 HandoffTool - 支持为子 Agent 指定模型提供商
"""
from typing import Generic, Optional
from dataclasses import dataclass, field

from astrbot.core.agent.agent import Agent
from astrbot.core.agent.run_context import TContext
from astrbot.core.agent.tool import FunctionTool
from astrbot.core.agent.hooks import BaseAgentRunHooks


@dataclass
class ConfigurableAgent(Generic[TContext]):
    """
    可配置的 Agent，支持指定模型提供商

    相比原版 Agent，增加了：
    - provider_id: 指定使用的模型提供商 ID
    - max_steps: 最大迭代步数
    """
    name: str
    instructions: str | None = None
    tools: list[str | FunctionTool] | None = None
    run_hooks: BaseAgentRunHooks[TContext] | None = None

    # 新增配置项
    provider_id: str | None = None  # 如果为 None，使用当前会话的提供商
    max_steps: int = 30


class ConfigurableHandoffTool(FunctionTool, Generic[TContext]):
    """
    可配置的 HandoffTool

    支持为子 Agent 指定不同的模型提供商
    """

    def __init__(
        self,
        agent: ConfigurableAgent[TContext],
        parameters: dict | None = None,
        **kwargs,
    ):
        self.agent = agent
        super().__init__(
            name=f"transfer_to_{agent.name}",
            parameters=parameters or self.default_parameters(),
            description=agent.instructions or self.default_description(agent.name),
            **kwargs,
        )

    def default_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "The input to be handed off to another agent. This should be a clear and concise request or task.",
                },
            },
        }

    def default_description(self, agent_name: str | None) -> str:
        agent_name = agent_name or "another"
        return f"Delegate tasks to {agent_name} agent to handle the request."
