"""
命令安全过滤器 - 白名单/黑名单机制
"""
import re
import shlex


class CommandFilter:
    """命令安全过滤器"""

    # 允许执行的命令白名单
    COMMAND_WHITELIST: dict[str, dict] = {
        # 文档转换
        "pandoc": {
            "description": "文档格式转换",
            "allowed_args": ["-f", "-t", "-o", "--from", "--to", "--output", "-s", "--standalone",
                           "--pdf-engine", "-V", "--variable", "--toc", "--toc-depth",
                           "--metadata", "--template", "--reference-doc", "--data-dir",
                           "--wrap", "--columns", "--number-sections", "--highlight-style"],
            "blocked_args": ["--lua-filter", "--filter", "--extract-media"],
            "max_timeout": 300,
        },
        # 图像处理 (ImageMagick)
        "convert": {
            "description": "图像格式转换和处理",
            "allowed_args": ["-resize", "-quality", "-format", "-rotate", "-flip", "-flop",
                           "-crop", "-thumbnail", "-strip", "-density"],
            "blocked_args": ["-write", "ephemeral:", "msl:", "-script", "-delegate"],
        },
        "magick": {
            "description": "ImageMagick 命令",
            "allowed_args": ["-resize", "-quality", "-format", "-rotate", "-flip", "-flop",
                           "-crop", "-thumbnail", "-strip", "-density"],
            "blocked_args": ["-write", "ephemeral:", "msl:", "-script", "-delegate"],
        },
        # 音视频处理
        "ffmpeg": {
            "description": "音视频处理",
            "allowed_args": ["-i", "-o", "-vf", "-af", "-c:v", "-c:a", "-b:v", "-b:a",
                           "-r", "-s", "-t", "-ss", "-to", "-y", "-n", "-f",
                           "-filter_complex", "-map", "-preset", "-crf", "-safe",
                           "-c", "-an", "-vn", "-shortest", "-loop"],
            "blocked_args": [],
            "max_timeout": 300,
        },
        "ffprobe": {
            "description": "音视频信息查看",
            "read_only": True,
        },
        # 文本处理（只读）
        "cat": {"description": "查看文件内容", "read_only": True},
        "head": {"description": "查看文件开头", "read_only": True},
        "tail": {"description": "查看文件结尾", "read_only": True},
        "wc": {"description": "统计文件", "read_only": True},
        "file": {"description": "查看文件类型", "read_only": True},
        # 压缩解压
        "zip": {
            "description": "压缩文件",
            "allowed_args": ["-r", "-q", "-9"],
            "blocked_args": [],
        },
        "unzip": {
            "description": "解压文件",
            "allowed_args": ["-o", "-d", "-q"],
            "blocked_args": [],
        },
        "tar": {
            "description": "打包/解包文件",
            "allowed_args": ["-c", "-x", "-z", "-v", "-f", "-C"],
            "blocked_args": [],
        },
        # PDF 处理 (poppler-utils)
        "pdftotext": {
            "description": "PDF 转文本",
            "read_only": True,
        },
        "pdfinfo": {
            "description": "查看 PDF 信息",
            "read_only": True,
        },
        "pdfimages": {
            "description": "提取 PDF 中的图片",
            "allowed_args": ["-j", "-png", "-all"],
            "blocked_args": [],
        },
        "pdftoppm": {
            "description": "PDF 转图片",
            "allowed_args": ["-png", "-jpeg", "-r", "-f", "-l"],
            "blocked_args": [],
        },
        # LibreOffice 文档转换
        "libreoffice": {
            "description": "Office 文档转换 (doc/docx/xls/xlsx/ppt/pptx)",
            "allowed_args": ["--headless", "--convert-to", "--outdir"],
            "blocked_args": ["--infilter", "--script"],
            "max_timeout": 300,
        },
        "soffice": {
            "description": "LibreOffice 命令 (别名)",
            "allowed_args": ["--headless", "--convert-to", "--outdir"],
            "blocked_args": ["--infilter", "--script"],
            "max_timeout": 300,
        },
        # Ghostscript PDF/PS 处理
        "gs": {
            "description": "PDF/PostScript 处理",
            "allowed_args": ["-dNOPAUSE", "-dBATCH", "-sDEVICE", "-sOutputFile",
                           "-r", "-dPDFSETTINGS", "-dCompatibilityLevel"],
            "blocked_args": ["-dSAFER=false", "-dDELAYSAFER"],
            "max_timeout": 300,
        },
        # Calibre 电子书转换
        "ebook-convert": {
            "description": "电子书格式转换 (epub/mobi/azw3/pdf)",
            "allowed_args": ["--output-profile", "--input-profile", "--cover",
                           "--title", "--authors", "--language"],
            "blocked_args": [],
            "max_timeout": 300,
        },
        "ebook-meta": {
            "description": "查看/编辑电子书元数据",
            "allowed_args": ["--title", "--authors", "--cover", "--get-cover"],
            "blocked_args": [],
        },
    }

    # 绝对禁止的命令黑名单
    COMMAND_BLACKLIST: list[str] = [
        # 系统危险命令
        "sudo", "su", "chmod", "chown", "chgrp", "chroot",
        "rm", "rmdir", "mkfs", "dd", "fdisk", "mount", "umount",
        "shutdown", "reboot", "init", "systemctl", "service",
        # 网络危险命令
        "curl", "wget", "nc", "netcat", "ssh", "scp", "rsync", "ftp", "sftp",
        "telnet", "nmap", "ping", "traceroute", "dig", "nslookup",
        # 进程控制
        "kill", "killall", "pkill", "nohup", "screen", "tmux",
        "ps", "top", "htop", "nice", "renice",
        # Shell 相关
        "bash", "sh", "zsh", "fish", "csh", "tcsh", "ksh", "dash",
        "eval", "exec", "source", ".", "alias", "unalias",
        # 包管理
        "apt", "apt-get", "yum", "dnf", "pacman", "brew",
        "pip", "pip3", "npm", "yarn", "gem", "cargo", "go",
        # 编程语言解释器
        "python", "python3", "python2", "node", "nodejs",
        "perl", "ruby", "php", "lua", "java", "javac",
        # 编辑器
        "vi", "vim", "nano", "emacs", "ed", "sed", "awk",
        # 其他危险命令
        "env", "export", "set", "unset", "printenv",
        "crontab", "at", "batch",
        "useradd", "userdel", "usermod", "groupadd", "passwd",
        "iptables", "firewall-cmd", "ufw",
        "docker", "podman", "kubectl",
        "git", "svn", "hg",  # 版本控制可能泄露信息
        "make", "cmake", "gcc", "g++", "clang",  # 编译器
        "ln", "link", "mklink",  # 符号链接
        "cp", "mv",  # 可能用于覆盖重要文件
    ]

    # 危险字符模式（注意：ffmpeg 的 filter_complex 中使用 | 作为分隔符，需要特殊处理）
    DANGEROUS_PATTERNS: list[str] = [
        r'(?<!")\|(?!")',  # 管道（但排除引号内的）- 简化为不检测，由其他机制保护
        r";",              # 命令分隔
        r"&&",             # 逻辑与
        r"\|\|",           # 逻辑或
        r"\$\(",           # 命令替换
        r"`",              # 反引号命令替换
        r"\$\{",           # 变量展开
        r"\$[A-Za-z_]",    # 环境变量
        r">\s*>",          # 追加重定向
        r"<\s*<",          # Here document
        r"&\s*$",          # 后台执行
        r"^~",             # 用户目录
    ]

    # 允许包含管道符的命令（如 ffmpeg 的 filter_complex）
    PIPE_ALLOWED_COMMANDS: list[str] = ["ffmpeg", "ffprobe"]

    def __init__(self, config: dict):
        """
        初始化命令过滤器

        Args:
            config: 插件配置
        """
        self.config = config
        self.command_timeout = config.get("command_timeout", 60)

        # 解析额外的白名单命令
        extra_cmds = config.get("extra_whitelist_commands", "")
        self.extra_whitelist: set[str] = set(
            c.strip() for c in extra_cmds.split(",") if c.strip()
        )

    def validate_command(self, command: str, user_workspace: str) -> tuple[bool, str]:
        """
        验证命令是否安全

        Args:
            command: 要执行的命令
            user_workspace: 用户工作区路径

        Returns:
            (是否安全, 错误信息或 "OK")
        """
        command = command.strip()

        if not command:
            return False, "命令不能为空"

        # 0. 先获取基础命令名（用于判断是否跳过某些检测）
        try:
            first_part = shlex.split(command)[0] if command else ""
        except ValueError:
            first_part = command.split()[0] if command.split() else ""

        # 1. 检查危险模式（对某些命令跳过管道符检测）
        for pattern in self.DANGEROUS_PATTERNS:
            # 对 ffmpeg 等命令跳过管道符检测（filter_complex 需要用 | 分隔）
            if pattern in [r'(?<!")\|(?!")', r"\|"] and first_part in self.PIPE_ALLOWED_COMMANDS:
                continue
            if re.search(pattern, command):
                return False, "检测到危险模式，命令被拒绝"

        # 2. 解析命令
        try:
            cmd_parts = shlex.split(command)
        except ValueError as e:
            return False, f"命令解析失败: {str(e)}"

        if not cmd_parts:
            return False, "命令不能为空"

        base_cmd = cmd_parts[0]

        # 3. 检查黑名单
        if base_cmd in self.COMMAND_BLACKLIST:
            return False, f"命令 '{base_cmd}' 被禁止执行"

        # 4. 检查白名单
        if base_cmd not in self.COMMAND_WHITELIST and base_cmd not in self.extra_whitelist:
            return False, f"命令 '{base_cmd}' 不在允许列表中。允许的命令: {', '.join(self.COMMAND_WHITELIST.keys())}"

        # 5. 检查命令特定的参数限制
        if base_cmd in self.COMMAND_WHITELIST:
            whitelist_config = self.COMMAND_WHITELIST[base_cmd]
            blocked_args = whitelist_config.get("blocked_args", [])

            for arg in cmd_parts[1:]:
                # 分离参数名和值（处理 --arg=value 格式）
                if "=" in arg:
                    param_name = arg.split("=")[0]
                else:
                    param_name = arg

                # 精确匹配检查，避免误匹配
                for blocked in blocked_args:
                    # 完全匹配或以 blocked= 开头
                    if param_name == blocked or param_name.startswith(blocked + "="):
                        return False, f"参数 '{param_name}' 被禁止使用"
                    # 对于特殊协议前缀（如 ephemeral:, msl:）检查是否包含
                    if ":" in blocked and blocked in arg:
                        return False, f"参数 '{arg}' 包含被禁止的内容"

        return True, "OK"

    def get_command_timeout(self, command: str) -> int:
        """
        获取命令的超时时间

        Args:
            command: 命令字符串

        Returns:
            超时时间（秒）
        """
        try:
            cmd_parts = shlex.split(command)
            base_cmd = cmd_parts[0] if cmd_parts else ""

            if base_cmd in self.COMMAND_WHITELIST:
                config = self.COMMAND_WHITELIST[base_cmd]
                return config.get("max_timeout", self.command_timeout)
        except (ValueError, IndexError):
            pass

        return self.command_timeout

    def get_allowed_commands(self) -> list[str]:
        """获取所有允许的命令列表"""
        commands = list(self.COMMAND_WHITELIST.keys())
        commands.extend(self.extra_whitelist)
        return sorted(set(commands))

    def get_command_description(self, cmd: str) -> str:
        """获取命令的描述"""
        if cmd in self.COMMAND_WHITELIST:
            return self.COMMAND_WHITELIST[cmd].get("description", "")
        return ""
