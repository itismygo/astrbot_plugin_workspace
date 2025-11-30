# AstrBot Workspace 插件

一个为 AstrBot 提供安全文件操作和命令执行能力的插件，支持多用户隔离工作区。

## 功能特性

- 用户隔离工作区：每个用户拥有独立的文件存储空间
- 文件操作：读取、写入、编辑、列出、重命名、删除
- 格式转换：文档、音视频、图片格式转换
- 文件发送：将处理结果发送给用户
- 内容搜索：在文件中搜索关键词
- 存储配额：限制每个用户的存储空间使用

## 目录结构

```
astrbot_plugin_workspace/
├── main.py                 # 主模块，LLM 工具定义
├── metadata.yaml           # 插件元数据
├── README.md              # 本文档
├── security/              # 安全模块
│   ├── __init__.py
│   ├── sandbox.py         # 路径沙箱
│   ├── permission.py      # 权限管理
│   └── command_filter.py  # 命令过滤
├── storage/               # 存储模块
│   ├── __init__.py
│   └── quota_manager.py   # 配额管理
├── tools/                 # 工具模块
│   ├── __init__.py
│   ├── summarizer_tools.py
│   └── search_tools.py
└── agents/                # Agent 定义
    ├── __init__.py
    ├── definitions.py     # 提示词定义
    └── orchestrator.py    # 多 Agent 编排
```

## 用户工作区结构

每个用户拥有独立的工作区：

```
user_workspaces/
└── {user_id}/
    ├── uploads/      # 用户上传的文件
    ├── outputs/      # 处理后的输出文件
    ├── documents/    # 文档目录
    ├── images/       # 图片目录
    └── temp/         # 临时文件
```

## 可用的 LLM 工具

| 工具名 | 功能 | 参数 |
|--------|------|------|
| read_file | 读取文件内容 | file_path, encoding, start_line, max_lines |
| write_file | 创建或写入文件 | file_path, content, encoding, mode |
| edit_file | 编辑文件内容 | file_path, old_content, new_content |
| list_files | 列出目录文件 | directory, recursive, pattern |
| rename_file | 重命名/移动文件 | old_path, new_path |
| delete_file | 删除文件 | file_path |
| send_file | 发送文件给用户 | file_path |
| execute_command | 执行白名单命令 | command, timeout |
| convert_pdf | PDF 转文本/MD/HTML | input_path, output_format |
| convert_office | Office 文档转换 | input_path, output_format |
| search_content | 搜索文件内容 | keyword, directory, file_pattern |
| summarize_batch | 批量读取文件 | directory, pattern, max_files |
| get_workspace_info | 查看工作区信息 | 无 |

## Docker 环境安装

### 必需依赖

```bash
# 进入容器
docker exec -it astrbot bash

# 更新源（使用清华镜像）
sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources
apt update

# 安装基础工具
apt install -y \
    poppler-utils \
    imagemagick \
    ffmpeg \
    zip unzip \
    file
```

### 文档转换工具

```bash
# Pandoc - 文档格式转换
apt install -y pandoc

# LibreOffice - Office 文档转换（推荐，中文支持好）
apt install -y libreoffice-writer-nogui libreoffice-calc-nogui libreoffice-impress-nogui

# 或者安装完整版（体积较大）
# apt install -y libreoffice --no-install-recommends
```

### 中文字体支持

```bash
# 安装中文字体（PDF 生成必需）
apt install -y fonts-noto-cjk fonts-wqy-microhei fonts-wqy-zenhei

# 刷新字体缓存
fc-cache -fv
```

### PDF 生成支持（可选）

```bash
# 如果需要用 pandoc 生成 PDF
apt install -y texlive-xetex texlive-lang-chinese
```

### 电子书转换（可选）

```bash
# Calibre - 电子书格式转换
apt install -y calibre
```

### 一键安装脚本

```bash
docker exec -it astrbot bash -c "
sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources && \
apt update && \
apt install -y \
    poppler-utils \
    imagemagick \
    ffmpeg \
    zip unzip \
    file \
    pandoc \
    libreoffice-writer-nogui \
    libreoffice-calc-nogui \
    libreoffice-impress-nogui \
    fonts-noto-cjk \
    fonts-wqy-microhei && \
fc-cache -fv
"
```

## 安全机制

### 1. 路径沙箱

- 所有文件操作限制在用户工作区内
- 防止路径遍历攻击（如 `../../../etc/passwd`）
- 符号链接检查，防止链接指向工作区外
- 严格的前缀检查，避免边界情况绕过

### 2. 命令过滤

白名单命令：
- 文档转换：pandoc, libreoffice, soffice
- 图像处理：convert, magick (ImageMagick)
- 音视频：ffmpeg, ffprobe
- PDF 处理：pdftotext, pdfinfo, pdftoppm, pdfimages
- 压缩解压：zip, unzip, tar
- 电子书：ebook-convert, ebook-meta
- 只读命令：cat, head, tail, wc, file

黑名单命令（绝对禁止）：
- 系统命令：sudo, su, rm, chmod, chown, shutdown, reboot
- 网络命令：curl, wget, nc, ssh, scp, ftp
- Shell：bash, sh, zsh, eval, exec
- 包管理：apt, pip, npm, yarn
- 编程语言：python, node, perl, ruby, php
- 编辑器：vi, vim, nano, sed, awk
- 其他危险命令：docker, git, make, gcc

### 3. 参数过滤

针对特定命令的危险参数：
- ImageMagick：禁止 `-write`, `-script`, `-delegate`, `ephemeral:`, `msl:`
- Pandoc：禁止 `--lua-filter`, `--filter`
- LibreOffice：禁止 `--infilter`, `--script`
- Ghostscript：禁止 `-dSAFER=false`, `-dDELAYSAFER`

### 4. 环境隔离

- 命令执行时只传递必要的环境变量（PATH, LANG, LC_ALL）
- HOME 和 TEMP 设置为用户工作区目录
- 防止环境变量泄露敏感信息

### 5. 存储配额

- 每用户默认 100MB 存储限制
- 写入文件前检查配额
- 可在配置中调整配额大小

## 安全风险说明

### 已知风险

1. **LibreOffice 宏执行**
   - 风险：恶意文档可能包含宏代码
   - 缓解：LibreOffice headless 模式默认不执行宏
   - 建议：不要处理来源不明的 Office 文档

2. **ImageMagick 漏洞**
   - 风险：历史上有多个 CVE 漏洞
   - 缓解：已禁止危险参数和协议
   - 建议：保持 ImageMagick 更新到最新版本

3. **FFmpeg 滤镜**
   - 风险：复杂滤镜可能导致资源耗尽
   - 缓解：设置命令超时（最大 5 分钟）
   - 建议：监控容器资源使用

4. **文件上传**
   - 风险：用户可能上传恶意文件
   - 缓解：文件隔离在用户工作区，不会自动执行
   - 建议：定期清理临时文件

### 安全建议

1. **定期更新**：保持所有依赖工具更新到最新版本
2. **资源限制**：为 Docker 容器设置 CPU 和内存限制
3. **日志监控**：定期检查日志中的异常操作
4. **备份数据**：定期备份重要数据
5. **权限控制**：使用白名单限制可使用插件的用户

## 配置选项

在 AstrBot 配置中可设置：

```yaml
plugins:
  workspace:
    user_quota_mb: 100          # 用户存储配额（MB）
    max_read_lines: 500         # 单次最大读取行数
    max_send_file_size_mb: 50   # 最大发送文件大小（MB）
    auto_save_uploaded_files: true  # 自动保存上传文件
    command_timeout: 60         # 命令默认超时（秒）
    enable_whitelist: false     # 是否启用用户白名单
    whitelist_users: []         # 白名单用户列表
    admin_users: []             # 管理员用户列表
```

## 使用示例

### 查看上传的文件

```
用户：我上传了什么文件？
助手：uploads有3个文件 report.pdf (1.81MB) data.xlsx (25KB) image.png (500KB)
```

### 文档格式转换

```
用户：把这个 Word 文档转成 PDF
助手：转换完成 已发送 report.pdf (2.5MB)
```

### 搜索文件内容

```
用户：在我的文件里搜索"会议纪要"
助手：找到2处匹配
文件: documents/notes.txt
>>> 行15: 2024年度会议纪要
```

## 故障排除

### 命令执行失败

1. 检查命令是否在白名单中
2. 检查是否安装了对应工具
3. 查看日志获取详细错误信息

### 文件转换失败

1. 检查输入文件格式是否正确
2. 检查是否安装了必要的字体
3. 尝试使用其他转换工具

### 中文乱码

1. 确认已安装中文字体
2. 运行 `fc-cache -fv` 刷新字体缓存
3. 重启 AstrBot 容器

## 许可证

MIT License

## 更新日志

### v2.0.0
- 多用户隔离工作区
- 安全沙箱机制
- 命令白名单/黑名单
- 存储配额管理
- 新增 convert_office 工具
- 优化提示词，简化回复格式
