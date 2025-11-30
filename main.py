"""
AstrBot Workspace 插件 - 安全工作区，提供文件操作和命令执行能力
支持多 Agent 架构，包括文件处理、命令执行、文件发送、批量总结、搜索分析等功能
"""
import os
import asyncio
import fnmatch
import shlex
import re
from datetime import datetime
from typing import List

from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.event.filter import EventMessageType
from astrbot.api.star import Context, Star, register, StarTools
from astrbot.api.message_components import Plain, Image, File, Video, Record
import astrbot.api.message_components as Comp
from astrbot.api import logger

from .security import PathSandbox, PermissionManager, CommandFilter
from .security.sandbox import SecurityError
from .storage import QuotaManager
from .tools import SummarizerTools, SearchTools
from .agents.orchestrator import create_sub_agents, create_handoff_tools


@register("workspace", "AstrBot", "安全工作区插件 - 多Agent架构，提供文件操作、命令执行等能力", "2.0.0")
class WorkspacePlugin(Star):
    """安全工作区插件 - 多 Agent 架构"""

    def __init__(self, context: Context, config: dict = None):
        super().__init__(context)
        self.config = config or {}
        self.tools = StarTools()  # 获取框架工具

        # 获取插件数据目录（get_data_dir() 返回的路径已包含插件名）
        self.data_dir = self.tools.get_data_dir()
        os.makedirs(self.data_dir, exist_ok=True)

        # 初始化安全模块
        self.sandbox = PathSandbox(self.data_dir)
        self.permission = PermissionManager(self.config)
        self.command_filter = CommandFilter(self.config)
        self.quota_manager = QuotaManager(
            self.data_dir,
            self.config.get("user_quota_mb", 100)
        )

        # 初始化新增工具
        self.summarizer_tools = SummarizerTools(self)
        self.search_tools = SearchTools(self)

        # 配置项
        self.max_read_lines = self.config.get("max_read_lines", 500)
        self.max_send_file_size = self.config.get("max_send_file_size_mb", 50) * 1024 * 1024
        self.auto_save_uploads = self.config.get("auto_save_uploaded_files", True)

        # 多 Agent 模式配置
        self.enable_multi_agent = self.config.get("enable_multi_agent", False)
        self.sub_agents = None
        self.handoff_tools = None

        logger.info(f"Workspace 插件 v2.0 已加载，数据目录: {self.data_dir}")

    async def initialize(self):
        """插件激活时调用，注册 HandoffTool"""
        await self._register_handoff_tools()

    async def terminate(self):
        """插件禁用时调用，清理 HandoffTool"""
        await self._unregister_handoff_tools()

    async def _register_handoff_tools(self):
        """注册 HandoffTool 到 AstrBot 的工具管理器（延迟注册）"""
        if not self.enable_multi_agent:
            return

        try:
            # 获取工具管理器
            from astrbot.core.provider.register import llm_tools as tool_manager

            # 创建子 Agent 和 HandoffTools
            self.sub_agents = create_sub_agents()
            self.handoff_tools = create_handoff_tools(self.sub_agents)

            # 注册 HandoffTools 到工具管理器
            for handoff_tool in self.handoff_tools:
                # 检查是否已存在
                existing = tool_manager.get_func(handoff_tool.name)
                if existing:
                    tool_manager.remove_func(handoff_tool.name)
                tool_manager.func_list.append(handoff_tool)
                logger.info(f"已注册 HandoffTool: {handoff_tool.name}")

            logger.info(f"多 Agent 模式已启用，注册了 {len(self.handoff_tools)} 个 HandoffTool")

        except Exception as e:
            logger.error(f"注册 HandoffTool 失败: {e}")

    async def _unregister_handoff_tools(self):
        """从 AstrBot 的工具管理器中移除 HandoffTool"""
        if not self.handoff_tools:
            return

        try:
            from astrbot.core.provider.register import llm_tools as tool_manager

            for handoff_tool in self.handoff_tools:
                tool_manager.remove_func(handoff_tool.name)
                logger.info(f"已移除 HandoffTool: {handoff_tool.name}")

            self.handoff_tools = None
            self.sub_agents = None

        except Exception as e:
            logger.error(f"移除 HandoffTool 失败: {e}")

    def _check_permission(self, event: AstrMessageEvent) -> tuple:
        """检查用户权限"""
        user_id = event.get_sender_id()
        user_role = getattr(event, 'role', '')
        return self.permission.check_permission(user_id, user_role)

    def _get_user_workspace(self, event: AstrMessageEvent) -> str:
        """获取用户工作区路径"""
        user_id = event.get_sender_id()
        return self.sandbox.get_user_workspace(user_id)

    def _format_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        return self.quota_manager.format_size(size_bytes)

    # ==================== LLM 工具 ====================

    @filter.llm_tool(name="read_file")
    async def read_file(
        self,
        event: AstrMessageEvent,
        file_path: str,
        encoding: str = "utf-8",
        start_line: int = 0,
        max_lines: int = 0
    ) -> str:
        """
        读取工作区内的文件内容。用于查看用户上传的文件、检查文件内容、分析文件格式等。

        使用场景：
        - 用户要求查看某个文件的内容
        - 需要分析文件内容以确定文件类型或格式
        - 读取配置文件、代码文件、文本文件等
        - 在编辑文件前先查看原内容

        注意事项：
        - 新上传的文件通常保存在 uploads/ 目录下，文件名格式为 时间戳_原文件名
        - 如果不确定文件位置，请先使用 list_files 工具查看目录结构
        - 对于大文件，使用 start_line 和 max_lines 参数分段读取
        - 二进制文件（如图片、视频）无法正确读取，请直接使用 send_file 发送

        Args:
            file_path (str): 文件路径（相对于工作区），如 "uploads/文件名" 或 "documents/test.txt"
            encoding (str): 文件编码，默认 utf-8，中文文件可能需要 gbk
            start_line (int): 起始行号（从0开始），用于读取大文件的部分内容
            max_lines (int): 最大读取行数，0表示使用默认值

        Returns:
            文件内容

        回复要求：不使用markdown格式 不使用星号或特殊符号 简洁直接回复
        """
        # 权限检查
        allowed, msg = self._check_permission(event)
        if not allowed:
            return f"权限不足: {msg}"

        workspace = self._get_user_workspace(event)
        max_lines = max_lines if max_lines > 0 else self.max_read_lines

        try:
            safe_path = self.sandbox.resolve_path(file_path, workspace)

            if not os.path.exists(safe_path):
                return f"文件不存在: {file_path}"

            if not os.path.isfile(safe_path):
                return f"路径不是文件: {file_path}"

            # 检查文件大小
            file_size = os.path.getsize(safe_path)
            if file_size > 10 * 1024 * 1024:  # 10MB
                return f"文件过大 ({self._format_size(file_size)})，请使用 start_line 和 max_lines 参数分段读取"

            with open(safe_path, 'r', encoding=encoding, errors='replace') as f:
                lines = f.readlines()

            total_lines = len(lines)
            selected_lines = lines[start_line:start_line + max_lines]
            content = ''.join(selected_lines)

            # 添加提示信息
            if total_lines > start_line + max_lines:
                content += f"\n\n[文件共 {total_lines} 行，已显示第 {start_line + 1}-{min(start_line + max_lines, total_lines)} 行]"

            return content

        except SecurityError as e:
            return f"安全错误: {str(e)}"
        except Exception as e:
            return f"读取文件失败: {str(e)}"

    @filter.llm_tool(name="write_file")
    async def write_file(
        self,
        event: AstrMessageEvent,
        file_path: str,
        content: str,
        encoding: str = "utf-8",
        mode: str = "overwrite"
    ) -> str:
        """
        在工作区内创建或写入文件。用于创建新文件、保存处理结果、生成输出文件等。

        使用场景：
        - 创建新的文本文件、代码文件、配置文件等
        - 保存转换或处理后的内容（如格式转换结果）
        - 生成报告、摘要等输出文件
        - 创建脚本文件供后续执行

        注意事项：
        - 建议将输出文件保存到 outputs/ 目录
        - 文件路径中的目录会自动创建
        - 使用 mode="append" 可以追加内容而不覆盖原文件
        - 写入后如需发送给用户，请使用 send_file 工具
        - 不要用此工具写入二进制内容

        Args:
            file_path (str): 文件路径（相对于工作区），如 "outputs/result.txt" 或 "documents/report.md"
            content (str): 要写入的文本内容
            encoding (str): 文件编码，默认 utf-8
            mode (str): 写入模式，"overwrite" 覆盖（默认）或 "append" 追加到末尾

        Returns:
            操作结果

        回复要求：不使用markdown格式 不使用星号或特殊符号 简洁直接回复
        """
        allowed, msg = self._check_permission(event)
        if not allowed:
            return f"权限不足: {msg}"

        workspace = self._get_user_workspace(event)
        user_id = event.get_sender_id()

        try:
            safe_path = self.sandbox.resolve_path(file_path, workspace)

            # 配额检查
            content_size = len(content.encode(encoding))
            quota_ok, quota_msg = self.quota_manager.check_quota(user_id, workspace, content_size)
            if not quota_ok:
                return quota_msg

            # 确保父目录存在
            parent_dir = os.path.dirname(safe_path)
            os.makedirs(parent_dir, exist_ok=True)

            # 写入文件
            write_mode = 'w' if mode == "overwrite" else 'a'
            with open(safe_path, write_mode, encoding=encoding) as f:
                f.write(content)

            return f"文件写入成功: {file_path} ({self._format_size(content_size)})"

        except SecurityError as e:
            return f"安全错误: {str(e)}"
        except Exception as e:
            return f"写入文件失败: {str(e)}"

    @filter.llm_tool(name="edit_file")
    async def edit_file(
        self,
        event: AstrMessageEvent,
        file_path: str,
        old_content: str,
        new_content: str,
        encoding: str = "utf-8"
    ) -> str:
        """
        编辑工作区内的文件，将指定内容替换为新内容。用于修改现有文件的部分内容。

        使用场景：
        - 修改文件中的特定文本或代码片段
        - 修复文件中的错误内容
        - 更新配置文件中的某个值
        - 替换文件中的关键词或字符串

        注意事项：
        - 必须先使用 read_file 查看文件内容，确保 old_content 精确匹配
        - old_content 必须与文件中的内容完全一致（包括空格、换行）
        - 如果要替换的内容在文件中出现多次，会全部替换
        - 如果需要完全重写文件，建议使用 write_file 而不是 edit_file

        Args:
            file_path (str): 文件路径（相对于工作区）
            old_content (str): 要被替换的原内容（必须精确匹配文件中的内容）
            new_content (str): 替换后的新内容
            encoding (str): 文件编码，默认 utf-8

        Returns:
            操作结果

        回复要求：不使用markdown格式 不使用星号或特殊符号 简洁直接回复
        """
        allowed, msg = self._check_permission(event)
        if not allowed:
            return f"权限不足: {msg}"

        workspace = self._get_user_workspace(event)

        try:
            safe_path = self.sandbox.resolve_path(file_path, workspace)

            if not os.path.exists(safe_path):
                return f"文件不存在: {file_path}"

            with open(safe_path, 'r', encoding=encoding, errors='replace') as f:
                content = f.read()

            if old_content not in content:
                return "未找到要替换的内容，请检查 old_content 是否正确"

            # 计算替换次数
            count = content.count(old_content)
            new_file_content = content.replace(old_content, new_content)

            with open(safe_path, 'w', encoding=encoding) as f:
                f.write(new_file_content)

            return f"文件编辑成功: {file_path}，替换了 {count} 处内容"

        except SecurityError as e:
            return f"安全错误: {str(e)}"
        except Exception as e:
            return f"编辑文件失败: {str(e)}"

    @filter.llm_tool(name="list_files")
    async def list_files(
        self,
        event: AstrMessageEvent,
        directory: str = ".",
        recursive: bool = False,
        pattern: str = "*"
    ) -> str:
        """
        列出工作区内的文件和目录。用于查看用户工作区的文件结构和内容。

        使用场景：
        - 查看用户上传了哪些文件（查看 uploads/ 目录）
        - 了解工作区的目录结构
        - 查找特定类型的文件（使用 pattern 参数）
        - 确认文件是否存在、获取文件大小和修改时间

        注意事项：
        - 用户新上传的文件保存在 uploads/ 目录
        - 处理后的输出文件通常在 outputs/ 目录
        - 使用 recursive=True 可以查看所有子目录
        - 使用 pattern 可以过滤文件，如 "*.txt" 只显示文本文件

        常用目录：
        - uploads/: 用户上传的文件
        - outputs/: 处理后的输出文件
        - documents/: 文档目录
        - images/: 图片目录
        - temp/: 临时文件

        Args:
            directory (str): 目录路径（相对于工作区），默认 "." 表示根目录
            recursive (bool): 是否递归列出子目录内容，默认 False
            pattern (str): 文件名匹配模式，支持通配符 * 和 ?，如 "*.pdf"

        Returns:
            文件和目录列表，包含文件大小和修改时间

        回复要求：不使用markdown格式 不使用星号或特殊符号 简洁直接回复
        """
        allowed, msg = self._check_permission(event)
        if not allowed:
            return f"权限不足: {msg}"

        workspace = self._get_user_workspace(event)

        try:
            safe_path = self.sandbox.resolve_path(directory, workspace)

            if not os.path.exists(safe_path):
                return f"目录不存在: {directory}"

            if not os.path.isdir(safe_path):
                return f"路径不是目录: {directory}"

            result = []

            if recursive:
                for root, dirs, files in os.walk(safe_path):
                    rel_root = os.path.relpath(root, workspace)
                    if rel_root == '.':
                        rel_root = ''

                    for name in sorted(dirs):
                        path = os.path.join(rel_root, name) if rel_root else name
                        result.append(f"[目录] {path}/")

                    for name in sorted(files):
                        if fnmatch.fnmatch(name, pattern):
                            full_path = os.path.join(root, name)
                            size = os.path.getsize(full_path)
                            mtime = datetime.fromtimestamp(os.path.getmtime(full_path))
                            path = os.path.join(rel_root, name) if rel_root else name
                            result.append(f"[文件] {path} ({self._format_size(size)}, {mtime:%Y-%m-%d %H:%M})")
            else:
                for name in sorted(os.listdir(safe_path)):
                    full_path = os.path.join(safe_path, name)
                    if os.path.isdir(full_path):
                        result.append(f"[目录] {name}/")
                    elif fnmatch.fnmatch(name, pattern):
                        size = os.path.getsize(full_path)
                        mtime = datetime.fromtimestamp(os.path.getmtime(full_path))
                        result.append(f"[文件] {name} ({self._format_size(size)}, {mtime:%Y-%m-%d %H:%M})")

            if not result:
                return f"目录为空或没有匹配的文件: {directory}"

            return "\n".join(result)

        except SecurityError as e:
            return f"安全错误: {str(e)}"
        except Exception as e:
            return f"列出文件失败: {str(e)}"

    @filter.llm_tool(name="rename_file")
    async def rename_file(
        self,
        event: AstrMessageEvent,
        old_path: str,
        new_path: str
    ) -> str:
        """
        重命名或移动工作区内的文件。可用于给文件添加正确的扩展名或整理文件。

        使用场景：
        - 给上传的文件添加正确的扩展名（如将 uploaded_file 改为 document.pdf）
        - 重命名文件为更有意义的名称
        - 将文件移动到其他目录（如从 uploads/ 移动到 documents/）
        - 整理工作区文件结构

        注意事项：
        - 用户上传的文件可能没有扩展名，需要先用 read_file 检查文件类型
        - 如果目标路径已存在同名文件，操作会失败
        - 可以同时重命名和移动文件（指定不同目录的新路径）
        - 目标目录会自动创建

        常见用法：
        - 添加扩展名: "uploads/20231130_file" -> "uploads/20231130_file.html"
        - 移动文件: "uploads/doc.pdf" -> "documents/doc.pdf"

        Args:
            old_path (str): 原文件路径（相对于工作区）
            new_path (str): 新文件路径（相对于工作区），可以包含新的文件名和目录

        Returns:
            操作结果

        回复要求：不使用markdown格式 不使用星号或特殊符号 简洁直接回复
        """
        allowed, msg = self._check_permission(event)
        if not allowed:
            return f"权限不足: {msg}"

        workspace = self._get_user_workspace(event)

        try:
            safe_old_path = self.sandbox.resolve_path(old_path, workspace)
            safe_new_path = self.sandbox.resolve_path(new_path, workspace)

            if not os.path.exists(safe_old_path):
                return f"文件不存在: {old_path}"

            if os.path.exists(safe_new_path):
                return f"目标文件已存在: {new_path}"

            # 确保目标目录存在
            new_dir = os.path.dirname(safe_new_path)
            os.makedirs(new_dir, exist_ok=True)

            # 重命名/移动文件
            os.rename(safe_old_path, safe_new_path)

            return f"文件重命名成功: {old_path} -> {new_path}"

        except SecurityError as e:
            return f"安全错误: {str(e)}"
        except Exception as e:
            return f"重命名文件失败: {str(e)}"

    @filter.llm_tool(name="delete_file")
    async def delete_file(
        self,
        event: AstrMessageEvent,
        file_path: str
    ) -> str:
        """
        删除工作区内的文件。用于清理不需要的文件或释放存储空间。

        使用场景：
        - 删除临时文件或中间处理文件
        - 清理用户不再需要的文件
        - 释放存储配额空间

        注意事项：
        - 删除操作不可恢复，请确认用户确实要删除
        - 只能删除文件，不能删除目录
        - 建议在删除前确认文件名和路径
        - 删除后会显示释放的存储空间大小

        Args:
            file_path (str): 要删除的文件路径（相对于工作区）

        Returns:
            操作结果，包含释放的存储空间大小

        回复要求：不使用markdown格式 不使用星号或特殊符号 简洁直接回复
        """
        allowed, msg = self._check_permission(event)
        if not allowed:
            return f"权限不足: {msg}"

        workspace = self._get_user_workspace(event)

        try:
            safe_path = self.sandbox.resolve_path(file_path, workspace)

            if not os.path.exists(safe_path):
                return f"文件不存在: {file_path}"

            if os.path.isdir(safe_path):
                return "不能删除目录，只能删除文件"

            file_size = os.path.getsize(safe_path)
            os.remove(safe_path)

            return f"文件删除成功: {file_path} (释放 {self._format_size(file_size)})"

        except SecurityError as e:
            return f"安全错误: {str(e)}"
        except Exception as e:
            return f"删除文件失败: {str(e)}"

    @filter.llm_tool(name="convert_pdf")
    async def convert_pdf(
        self,
        event: AstrMessageEvent,
        input_path: str,
        output_format: str = "txt"
    ) -> str:
        """
        将 PDF 文件转换为其他格式（文本、Markdown、HTML）。仅支持 PDF 文件。

        使用场景：
        - 用户上传了 PDF 文件并希望提取文本内容
        - 需要将 PDF 转换为可编辑的格式
        - 提取 PDF 中的文字用于分析或处理

        注意事项：
        - 此工具仅支持 PDF 文件，不支持其他格式（如 HTML、Word 等）
        - 如果文件不是 PDF 格式，请使用其他方法处理（如 read_file 读取文本文件）
        - 转换后的文件会保存到 outputs/ 目录
        - 转换成功后请使用 send_file 将结果发送给用户
        - 扫描版 PDF（图片型）可能无法正确提取文字

        Args:
            input_path (str): PDF 文件路径（相对于工作区），如 "uploads/document.pdf"
            output_format (str): 输出格式，支持 "txt"（纯文本）、"md"（Markdown）、"html"

        Returns:
            转换结果，成功时会提示输出文件路径

        回复要求：不使用markdown格式 不使用星号或特殊符号 简洁直接回复
        """
        allowed, msg = self._check_permission(event)
        if not allowed:
            return f"权限不足: {msg}"

        workspace = self._get_user_workspace(event)

        try:
            safe_input = self.sandbox.resolve_path(input_path, workspace)

            if not os.path.exists(safe_input):
                return f"文件不存在: {input_path}"

            # 生成输出文件名
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            output_ext = output_format.lower()
            if output_ext not in ["txt", "md", "html"]:
                return f"不支持的输出格式: {output_format}，支持 txt/md/html"

            output_name = f"{base_name}.{output_ext}"
            output_dir = os.path.join(workspace, "outputs")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, output_name)

            # 使用 pdftotext 提取文本
            process = await asyncio.create_subprocess_exec(
                "pdftotext", "-layout", safe_input, "-",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=120
            )

            if process.returncode != 0:
                error = stderr.decode('utf-8', errors='replace')
                return f"PDF 转换失败 无法完成此操作: {error[:100]}"  # 截断错误信息，告知无法完成

            text_content = stdout.decode('utf-8', errors='replace')

            # 根据输出格式处理
            if output_ext == "txt":
                final_content = text_content
            elif output_ext == "md":
                # 简单的 Markdown 格式化
                lines = text_content.split('\n')
                final_content = f"# {base_name}\n\n" + '\n'.join(lines)
            elif output_ext == "html":
                # 简单的 HTML 格式化
                escaped_text = text_content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                final_content = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{base_name}</title></head>
<body><pre>{escaped_text}</pre></body>
</html>"""

            # 写入输出文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(final_content)

            return f"PDF 转换成功，文件已保存到: outputs/{output_name}。请立即使用 send_file 工具将此文件发送给用户，不要读取文件内容。"

        except asyncio.TimeoutError:
            return "PDF 转换超时 请稍后重试或尝试较小的文件"
        except Exception as e:
            return f"PDF 转换失败 无法完成: {str(e)[:100]}"

    @filter.llm_tool(name="convert_office")
    async def convert_office(
        self,
        event: AstrMessageEvent,
        input_path: str,
        output_format: str = "pdf"
    ) -> str:
        """
        使用 LibreOffice 转换 Office 文档为其他格式。对中文支持良好，推荐用于文档转 PDF。

        使用场景：
        - 将 doc/docx 文档转换为 PDF（推荐，中文支持好）
        - 将 Excel 表格转换为 PDF
        - 将 PPT 演示文稿转换为 PDF
        - Office 文档格式互转

        支持的输入格式：
        - Word: doc, docx, odt, rtf
        - Excel: xls, xlsx, ods, csv
        - PowerPoint: ppt, pptx, odp

        Args:
            input_path (str): 输入文件路径（相对于工作区），如 "uploads/文档.docx"
            output_format (str): 输出格式，支持 pdf/docx/html/txt，默认 pdf

        Returns:
            转换结果

        回复要求：不使用markdown格式 不使用星号或特殊符号 简洁直接回复
        """
        allowed, msg = self._check_permission(event)
        if not allowed:
            return f"权限不足: {msg}"

        workspace = self._get_user_workspace(event)

        try:
            safe_input = self.sandbox.resolve_path(input_path, workspace)

            if not os.path.exists(safe_input):
                return f"文件不存在: {input_path}"

            # 检查输出格式
            output_format = output_format.lower()
            supported_formats = ["pdf", "docx", "html", "txt"]
            if output_format not in supported_formats:
                return f"不支持的输出格式: {output_format}，支持 {'/'.join(supported_formats)}"

            # 准备输出目录
            output_dir = os.path.join(workspace, "outputs")
            os.makedirs(output_dir, exist_ok=True)

            # 使用 LibreOffice 转换
            process = await asyncio.create_subprocess_exec(
                "soffice",
                "--headless",
                "--convert-to", output_format,
                "--outdir", output_dir,
                safe_input,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=180
            )

            if process.returncode != 0:
                error = stderr.decode('utf-8', errors='replace')
                return f"转换失败: {error[:100]}"

            # 获取输出文件名
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            # 处理时间戳前缀的文件名
            if '_' in base_name and base_name.split('_')[0].isdigit():
                # 去掉时间戳前缀，如 20251130_082851_文档 -> 文档
                parts = base_name.split('_', 2)
                if len(parts) >= 3:
                    base_name = parts[2]
            output_name = f"{base_name}.{output_format}"
            output_path = os.path.join(output_dir, output_name)

            # LibreOffice 可能使用原始文件名，检查并重命名
            original_output = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(safe_input))[0]}.{output_format}")
            if os.path.exists(original_output) and original_output != output_path:
                os.rename(original_output, output_path)

            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                return f"转换成功: outputs/{output_name} ({self._format_size(file_size)})"
            else:
                return "转换完成但未找到输出文件"

        except asyncio.TimeoutError:
            return "转换超时 请尝试较小的文件"
        except FileNotFoundError:
            return "LibreOffice 未安装 无法执行转换"
        except Exception as e:
            return f"转换失败: {str(e)[:100]}"

    @filter.llm_tool(name="execute_command")
    async def execute_command(
        self,
        event: AstrMessageEvent,
        command: str,
        timeout: int = 0
    ) -> str:
        """
        在工作区内执行安全命令。仅支持白名单中的命令，用于文件格式转换等操作。

        使用场景：
        - 使用 pandoc 进行文档格式转换（如 HTML 转 Markdown、Word 转 PDF 等）
        - 使用 ffmpeg 进行音视频处理
        - 使用 convert/magick 进行图片处理
        - 执行 python 脚本处理文件

        可用命令示例：
        - pandoc input.html -o output.md（HTML 转 Markdown）
        - pandoc input.md -o output.pdf（Markdown 转 PDF）
        - pandoc input.docx -o output.md（Word 转 Markdown）
        - ffmpeg -i input.mp4 output.mp3（视频转音频）
        - python script.py（执行 Python 脚本）

        注意事项：
        - 只能执行白名单中的命令，不支持任意 shell 命令
        - 文件路径相对于工作区，会自动转换为绝对路径
        - 如果命令执行失败，请检查命令语法和文件路径
        - 转换后的文件需要使用 send_file 发送给用户
        - 使用 get_workspace_info 可以查看所有可用命令

        Args:
            command (str): 要执行的命令，如 "pandoc uploads/file.html -o outputs/file.md"
            timeout (int): 超时时间（秒），0 表示使用默认值，最大 300 秒

        Returns:
            命令执行结果（输出内容或错误信息）

        回复要求：不使用markdown格式 不使用星号或特殊符号 简洁直接回复
        """
        allowed, msg = self._check_permission(event)
        if not allowed:
            return f"权限不足: {msg}"

        workspace = self._get_user_workspace(event)

        # 验证命令安全性
        valid, error_msg = self.command_filter.validate_command(command, workspace)
        if not valid:
            return f"命令验证失败: {error_msg}"

        # 获取超时时间（处理 LLM 可能传递字符串的情况）
        try:
            timeout = int(timeout) if timeout else 0
        except (ValueError, TypeError):
            timeout = 0
        cmd_timeout = timeout if timeout > 0 else self.command_filter.get_command_timeout(command)
        cmd_timeout = min(cmd_timeout, 300)  # 最大 5 分钟

        try:
            # 解析命令
            cmd_parts = shlex.split(command)

            # 处理路径参数，转换为绝对路径
            processed_parts = [cmd_parts[0]]
            for arg in cmd_parts[1:]:
                if not arg.startswith('-'):
                    # 可能是文件路径，尝试解析
                    try:
                        safe_arg = self.sandbox.resolve_path(arg, workspace)
                        processed_parts.append(safe_arg)
                    except SecurityError as e:
                        # 安全错误：路径解析失败时拒绝执行，而不是使用原参数
                        return f"路径安全检查失败: {arg} - {str(e)}"
                else:
                    processed_parts.append(arg)

            # 执行命令
            process = await asyncio.create_subprocess_exec(
                *processed_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workspace,
                env=self._get_safe_env(workspace)
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=cmd_timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return f"命令执行超时（{cmd_timeout}秒）"

            result = []
            if stdout:
                output = stdout.decode('utf-8', errors='replace').strip()
                if output:
                    result.append(f"输出:\n{output}")
            if stderr:
                error = stderr.decode('utf-8', errors='replace').strip()
                if error:
                    result.append(f"错误:\n{error}")
            if process.returncode != 0:
                result.append(f"返回码: {process.returncode}")

            return "\n".join(result) if result else "命令执行成功（无输出）"

        except FileNotFoundError:
            return f"命令未找到 无法执行: {cmd_parts[0]} 未安装 请告知用户此功能不可用"
        except Exception as e:
            return f"命令执行失败 无法完成: {str(e)[:100]}"

    def _get_safe_env(self, workspace: str = None) -> dict:
        """获取安全的环境变量"""
        # 只保留必要的环境变量，避免泄露敏感信息
        safe_env = {}
        for key in ['PATH', 'LANG', 'LC_ALL']:
            if key in os.environ:
                safe_env[key] = os.environ[key]
        # 设置安全的临时目录（使用工作区内的 temp 目录）
        if workspace:
            temp_dir = os.path.join(workspace, 'temp')
            safe_env['HOME'] = workspace
            safe_env['TEMP'] = temp_dir
            safe_env['TMP'] = temp_dir
        return safe_env

    @filter.llm_tool(name="send_file")
    async def send_file(
        self,
        event: AstrMessageEvent,
        file_path: str
    ) -> str:
        """
        将工作区内的文件发送给用户。这是向用户交付文件的主要方式。

        使用场景：
        - 发送转换后的文件（如 PDF 转换结果、格式转换输出等）
        - 发送用户请求的文件
        - 发送处理后的图片、文档等
        - 发送生成的报告或输出文件

        注意事项：
        - 这是向用户发送文件的唯一方式，不要尝试在消息中输出文件内容
        - 图片文件会以图片形式发送，其他文件以文件形式发送
        - 文件大小有限制，超大文件可能无法发送
        - 转换或处理完成后，应立即使用此工具发送结果给用户
        - 不要先读取文件内容再发送，直接使用此工具发送文件

        支持的图片格式（会以图片显示）：
        - PNG、JPG、JPEG、GIF、BMP、WEBP

        Args:
            file_path (str): 文件路径（相对于工作区），如 "outputs/result.md" 或 "uploads/image.png"

        Returns:
            发送结果

        回复要求：不使用markdown格式 不使用星号或特殊符号 简洁直接回复
        """
        allowed, msg = self._check_permission(event)
        if not allowed:
            return f"权限不足: {msg}"

        workspace = self._get_user_workspace(event)

        try:
            safe_path = self.sandbox.resolve_path(file_path, workspace)

            if not os.path.exists(safe_path):
                return f"文件不存在: {file_path}"

            if not os.path.isfile(safe_path):
                return f"路径不是文件: {file_path}"

            file_name = os.path.basename(safe_path)
            file_size = os.path.getsize(safe_path)

            # 检查文件大小限制
            if file_size > self.max_send_file_size:
                return f"文件过大 ({self._format_size(file_size)})，超过发送限制 ({self._format_size(self.max_send_file_size)})"

            # 判断文件类型
            image_exts = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']
            is_image = any(file_name.lower().endswith(ext) for ext in image_exts)

            # 使用主动消息发送文件
            logger.info(f"准备发送文件: {file_name}, 路径: {safe_path}")
            umo = event.unified_msg_origin

            if is_image:
                # 图片使用 fromFileSystem
                logger.info(f"发送图片: {safe_path}")
                chain = [Comp.Image.fromFileSystem(safe_path)]
                await self.context.send_message(umo, MessageChain(chain))
                return f"图片发送成功: {file_name}"
            else:
                # 普通文件
                logger.info(f"发送文件: {safe_path}")
                chain = [Comp.File(file=safe_path, name=file_name)]
                await self.context.send_message(umo, MessageChain(chain))
                return f"文件发送成功: {file_name} ({self._format_size(file_size)})"

        except SecurityError as e:
            return f"安全错误: {str(e)}"
        except Exception as e:
            logger.error(f"发送文件失败: {str(e)}", exc_info=True)
            return f"发送文件失败: {str(e)}"

    @filter.llm_tool(name="get_workspace_info")
    async def get_workspace_info(
        self,
        event: AstrMessageEvent
    ) -> str:
        """
        获取当前用户的工作区信息，包括存储使用情况和可用命令列表。

        使用场景：
        - 查看用户的存储配额使用情况
        - 了解有哪些命令可以使用（用于 execute_command）
        - 获取工作区的目录结构说明
        - 在开始处理任务前了解环境信息

        返回信息包括：
        - 用户 ID 和工作区路径
        - 存储配额：已使用、总配额、剩余空间、使用率
        - 可用命令列表（如 pandoc、ffmpeg、python 等）
        - 标准目录结构说明

        Returns:
            工作区详细信息

        回复要求：不使用markdown格式 不使用星号或特殊符号 简洁直接回复
        """
        allowed, msg = self._check_permission(event)
        if not allowed:
            return f"权限不足: {msg}"

        workspace = self._get_user_workspace(event)
        user_id = event.get_sender_id()

        # 获取配额信息
        quota_info = self.quota_manager.get_quota_info(user_id, workspace)

        # 获取可用命令
        commands = self.command_filter.get_allowed_commands()

        info = [
            "=== 工作区信息 ===",
            f"用户ID: {user_id}",
            f"工作区路径: {workspace}",
            "",
            "=== 存储配额 ===",
            f"已使用: {quota_info['used_mb']} MB",
            f"总配额: {quota_info['quota_mb']} MB",
            f"剩余: {quota_info['remaining_mb']} MB",
            f"使用率: {quota_info['usage_percent']}%",
            "",
            "=== 可用命令 ===",
            ", ".join(commands),
            "",
            "=== 目录结构 ===",
            "documents/ - 文档目录",
            "images/ - 图片目录",
            "outputs/ - 输出目录",
            "temp/ - 临时文件",
            "uploads/ - 上传文件",
        ]

        return "\n".join(info)

    # ==================== 文件上传自动保存 ====================

    @filter.event_message_type(EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """处理消息，自动保存上传的文件"""
        if not self.auto_save_uploads:
            return

        # 检查权限
        allowed, _ = self._check_permission(event)
        if not allowed:
            return

        # 检查消息中是否有文件
        message = event.message_obj
        if not message or not hasattr(message, 'message'):
            return

        for component in message.message:
            # 保存文件、图片、视频、语音
            if isinstance(component, (File, Image, Video, Record)):
                await self._save_uploaded_media(event, component)

    async def _save_uploaded_media(self, event: AstrMessageEvent, component):
        """保存上传的媒体文件（文件、图片、视频、语音）到用户工作区"""
        try:
            workspace = self._get_user_workspace(event)
            uploads_dir = os.path.join(workspace, "uploads")

            # 根据组件类型获取 URL 和默认扩展名
            file_url = None
            file_path_local = None
            default_ext = ''
            type_name = 'file'
            file_name = 'uploaded_file'

            # 尝试使用 get_file() 异步获取文件路径
            if hasattr(component, 'get_file'):
                try:
                    file_path_local = await component.get_file()
                except Exception as e:
                    logger.debug(f"get_file() 失败: {e}")

            if isinstance(component, File):
                file_url = getattr(component, 'url', None)
                # 调试：查看 File 组件的所有属性
                logger.info(f"[调试] File组件属性: name={getattr(component, 'name', None)}, url={file_url}, file={getattr(component, 'file', None)}")
                logger.info(f"[调试] File组件__dict__: {getattr(component, '__dict__', {})}")
                # 只从 name 属性获取文件名，避免触发同步下载
                file_name = getattr(component, 'name', None) or 'uploaded_file'
                type_name = 'file'
            elif isinstance(component, Image):
                file_url = getattr(component, 'url', None)
                file_name = 'image'
                default_ext = '.jpg'
                type_name = 'image'
            elif isinstance(component, Video):
                file_url = getattr(component, 'url', None)
                file_name = 'video'
                default_ext = '.mp4'
                type_name = 'video'
            elif isinstance(component, Record):
                file_url = getattr(component, 'url', None)
                file_name = 'audio'
                default_ext = '.wav'
                type_name = 'audio'

            # 如果 file_name 是路径，提取文件名部分
            if file_name and ('/' in file_name or '\\' in file_name):
                file_name = os.path.basename(file_name)

            # 如果没有 URL 也没有本地路径，跳过
            if not file_url and not file_path_local:
                return

            # 从文件名获取扩展名（适配器已修复，file_name 应包含正确扩展名）
            _, ext = os.path.splitext(file_name)
            if not ext:
                ext = default_ext

            # 生成唯一文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(file_name)[0]
            base_name = re.sub(r'[<>:"/\\|?*]', '_', base_name)
            # 安全检查：防止特殊目录名
            if base_name in ['.', '..', '']:
                base_name = 'uploaded_file'
            save_name = f"{timestamp}_{base_name}{ext}"
            save_path = os.path.join(uploads_dir, save_name)

            # 优先从本地路径复制，否则从 URL 下载
            if file_path_local and os.path.exists(file_path_local):
                # 安全检查：防止符号链接攻击
                if os.path.islink(file_path_local):
                    logger.warning(f"拒绝复制符号链接: {file_path_local}")
                    return
                import shutil
                shutil.copy2(file_path_local, save_path)
                logger.info(f"{type_name} 已保存 (本地复制): {save_path} [原名: {file_name}]")
            elif file_url:
                import aiohttp
                # 设置超时，防止大文件下载阻塞
                timeout = aiohttp.ClientTimeout(total=60)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(file_url) as response:
                        if response.status == 200:
                            content = await response.read()
                            with open(save_path, 'wb') as f:
                                f.write(content)
                            logger.info(f"{type_name} 已保存 (URL下载): {save_path} [原名: {file_name}]")
                        else:
                            logger.warning(f"下载失败，状态码: {response.status}")
            else:
                logger.warning(f"无法保存 {type_name}：没有可用的文件路径或 URL")

        except Exception as e:
            logger.error(f"保存上传媒体失败: {str(e)}")

    # ==================== 新增工具：批量总结和搜索 ====================

    @filter.llm_tool(name="summarize_batch")
    async def summarize_batch(
        self,
        event: AstrMessageEvent,
        directory: str = ".",
        pattern: str = "*",
        max_files: int = 10
    ) -> str:
        """
        批量读取目录中的文件并返回内容摘要，用于快速了解多个文件的内容。

        使用场景：
        - 快速浏览目录中多个文件的内容概要
        - 了解用户上传的多个文件分别包含什么内容
        - 在处理批量文件前先了解文件内容
        - 查找特定内容可能在哪个文件中

        注意事项：
        - 每个文件只读取前 2000 个字符作为预览
        - 适合文本文件，二进制文件无法正确显示
        - 如果需要完整读取某个文件，请使用 read_file
        - 使用 pattern 可以只查看特定类型的文件

        Args:
            directory (str): 目录路径（相对于工作区），默认 "." 表示根目录，常用 "uploads/"
            pattern (str): 文件匹配模式，支持通配符，如 "*.txt"、"*.md"、"report*"
            max_files (int): 最大处理文件数，默认 10 个，避免输出过长

        Returns:
            各文件的内容预览摘要

        回复要求：不使用markdown格式 不使用星号或特殊符号 简洁直接回复
        """
        allowed, msg = self._check_permission(event)
        if not allowed:
            return f"权限不足: {msg}"

        workspace = self._get_user_workspace(event)

        try:
            return await self.summarizer_tools.summarize_batch(
                workspace=workspace,
                directory=directory,
                pattern=pattern,
                max_files=max_files
            )
        except Exception as e:
            return f"批量读取失败: {str(e)}"

    @filter.llm_tool(name="search_content")
    async def search_content(
        self,
        event: AstrMessageEvent,
        keyword: str,
        directory: str = ".",
        file_pattern: str = "*",
        max_results: int = 20
    ) -> str:
        """
        在工作区文件中搜索关键词，返回匹配的文件和内容片段。用于在多个文件中查找特定内容。

        使用场景：
        - 在用户的文件中查找特定关键词或内容
        - 定位包含某个信息的文件
        - 搜索代码中的函数名、变量名等
        - 查找文档中的特定段落或引用

        注意事项：
        - 搜索不区分大小写
        - 会显示匹配行及其上下文（前后各 2 行）
        - 只搜索文本文件，二进制文件会被跳过
        - 使用 file_pattern 可以限制搜索范围，提高效率

        Args:
            keyword (str): 要搜索的关键词或短语
            directory (str): 搜索目录（相对于工作区），默认 "." 搜索整个工作区
            file_pattern (str): 文件匹配模式，如 "*.txt" 只搜索文本文件，"*.py" 只搜索 Python 文件
            max_results (int): 最大结果数，默认 20 条，避免输出过长

        Returns:
            搜索结果，包含文件名、行号和匹配内容的上下文

        回复要求：不使用markdown格式 不使用星号或特殊符号 简洁直接回复
        """
        allowed, msg = self._check_permission(event)
        if not allowed:
            return f"权限不足: {msg}"

        workspace = self._get_user_workspace(event)

        try:
            return await self.search_tools.search_content(
                workspace=workspace,
                keyword=keyword,
                directory=directory,
                file_pattern=file_pattern,
                max_results=max_results
            )
        except Exception as e:
            return f"搜索失败: {str(e)}"

    # ==================== Orchestrator 入口（可选） ====================
    #
    # 说明：当前插件的所有工具（read_file, write_file, execute_command 等）
    # 已经直接注册为 LLM 工具，LLM 可以直接调用它们。
    #
    # 如果你想要启用完整的多 Agent 架构（中枢 Agent 协调子 Agent），
    # 需要在 AstrBot 的 Agent 配置中使用 HandoffTool。
    #
    # 示例配置（在 AstrBot 主配置或自定义 Agent 中）：
    # ```python
    # from astrbot.core.agent.agent import Agent
    # from astrbot.core.agent.handoff import HandoffTool
    # from astrbot_plugin_workspace.agents import create_sub_agents, create_handoff_tools
    #
    # # 创建子 Agent 和 HandoffTools
    # sub_agents = create_sub_agents()
    # handoff_tools = create_handoff_tools(sub_agents)
    #
    # # 将 handoff_tools 添加到主 Agent 的工具列表中
    # ```
    #
    # 当前模式：直接工具调用（单 Agent + 多工具）
    # - LLM 直接调用 read_file, write_file, execute_command 等
    # - 简单高效，适合大多数场景
    #
    # 多 Agent 模式：中枢协调（Orchestrator + 子 Agents）
    # - LLM 调用 transfer_to_file_agent, transfer_to_command_agent 等
    # - 子 Agent 有独立的系统提示词和工具集
    # - 适合复杂任务分解和专业化处理
