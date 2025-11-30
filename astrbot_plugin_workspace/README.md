# AstrBot Workspace 插件

一个为 AstrBot 提供安全文件操作、命令执行和新闻验证能力的插件，支持多用户隔离工作区。

## 功能特性

### 核心功能
- **用户隔离工作区**：每个用户拥有独立的文件存储空间
- **文件操作**：读取、写入、编辑、列出、重命名、删除
- **格式转换**：文档、音视频、图片格式转换
- **文件发送**：将处理结果发送给用户
- **内容搜索**：在文件中搜索关键词
- **存储配额**：限制每个用户的存储空间使用
- **定时清理**：自动清理过期临时文件

### 新闻验证功能 (v2.1.0 新增)
- **事实提取**：从新闻文本中自动提取可验证的事实点
- **来源评估**：基于白名单/黑名单 + 动态检查评估来源可信度
- **新闻验证**：综合评估新闻真实性，生成验证结论
- **PDF 报告**：生成详细的验证报告（支持中文）
- **网页截图**：截取证据网页作为存档

### 多 Agent 架构
- **文件处理 Agent**：专注文件操作任务
- **命令执行 Agent**：安全执行白名单命令
- **代码分析 Agent**：分析代码结构、生成文档
- **任务规划 Agent**：复杂任务拆解和项目规划
- **新闻验证 Agent**：验证新闻真实性
- **并行调度**：支持多 Agent 并行执行

## 目录结构

```
astrbot_plugin_workspace/
├── main.py                 # 主模块，LLM 工具定义
├── metadata.yaml           # 插件元数据
├── _conf_schema.json       # 配置项定义
├── requirements.txt        # Python 依赖
├── ruff.toml              # 代码规范配置
├── README.md              # 本文档
├── security/              # 安全模块
│   ├── __init__.py
│   ├── sandbox.py         # 路径沙箱
│   ├── permission.py      # 权限管理
│   └── command_filter.py  # 命令过滤
├── storage/               # 存储模块
│   ├── __init__.py
│   ├── quota_manager.py   # 配额管理
│   └── cleaner.py         # 定时清理
├── tools/                 # 工具模块
│   ├── __init__.py
│   ├── summarizer_tools.py    # 批量总结
│   ├── search_tools.py        # 内容搜索
│   ├── fact_extractor.py      # 事实提取器
│   ├── fact_check_tools.py    # 新闻验证工具
│   ├── news_analyzer.py       # 新闻分析引擎
│   ├── report_generator.py    # PDF 报告生成
│   └── screenshot_tool.py     # 网页截图
├── credibility/           # 可信度评估模块
│   ├── __init__.py
│   ├── evaluator.py       # 可信度评估器
│   ├── source_registry.py # 来源注册表（白名单/黑名单）
│   └── dynamic_checker.py # 动态检查（HTTPS/域名年龄/ICP）
├── agents/                # Agent 定义
│   ├── __init__.py
│   ├── definitions.py     # 提示词定义
│   ├── orchestrator.py    # 多 Agent 编排
│   ├── parallel_dispatcher.py  # 并行调度器
│   └── custom_handoff.py  # 自定义 HandoffTool
├── hooks/                 # 钩子模块
│   ├── __init__.py
│   └── orchestrator_hooks.py
├── errors/                # 错误处理
│   ├── __init__.py
│   └── handler.py
└── utils/                 # 工具函数
    ├── __init__.py
    └── text_cleaner.py
```

## 用户工作区结构

每个用户拥有独立的工作区：

```
user_workspaces/
└── {user_id}/
    ├── uploads/      # 用户上传的文件
    ├── outputs/      # 处理后的输出文件
    │   ├── reports/      # 验证报告
    │   └── screenshots/  # 网页截图
    ├── documents/    # 文档目录
    ├── images/       # 图片目录
    └── temp/         # 临时文件
```

## 可用的 LLM 工具

### 文件操作工具

| 工具名 | 功能 | 参数 |
|--------|------|------|
| read_file | 读取文件内容 | file_path, encoding, start_line, max_lines |
| write_file | 创建或写入文件 | file_path, content, encoding, mode |
| edit_file | 编辑文件内容 | file_path, old_content, new_content |
| list_files | 列出目录文件 | directory, recursive, pattern |
| rename_file | 重命名/移动文件 | old_path, new_path |
| delete_file | 删除文件 | file_path |
| send_file | 发送文件给用户 | file_path |

### 转换和执行工具

| 工具名 | 功能 | 参数 |
|--------|------|------|
| execute_command | 执行白名单命令 | command, timeout |
| convert_pdf | PDF 转文本/MD/HTML | input_path, output_format |
| convert_office | Office 文档转换 | input_path, output_format |

### 搜索和总结工具

| 工具名 | 功能 | 参数 |
|--------|------|------|
| search_content | 搜索文件内容 | keyword, directory, file_pattern |
| summarize_batch | 批量读取文件 | directory, pattern, max_files |
| get_workspace_info | 查看工作区信息 | 无 |

### 新闻验证工具

| 工具名 | 功能 | 参数 |
|--------|------|------|
| extract_facts | 提取可验证事实点 | text, min_verifiability |
| evaluate_sources | 评估来源可信度 | search_results, claim |
| verify_news | 完整新闻验证 | news_text, search_results, generate_report, take_screenshots |
| get_verification_plan | 获取验证计划 | news_text |

### 多 Agent 工具

| 工具名 | 功能 | 参数 |
|--------|------|------|
| parallel_agents | 并行调用多个 Agent | tasks |

## 安装

### Python 依赖

```bash
pip install aiohttp playwright weasyprint
playwright install chromium
```

### Docker 环境安装

#### 必需依赖

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

#### 文档转换工具

```bash
# Pandoc - 文档格式转换
apt install -y pandoc

# LibreOffice - Office 文档转换（推荐，中文支持好）
apt install -y libreoffice-writer-nogui libreoffice-calc-nogui libreoffice-impress-nogui
```

#### 中文字体支持

```bash
# 安装中文字体（PDF 生成必需）
apt install -y fonts-noto-cjk fonts-wqy-microhei fonts-wqy-zenhei

# 刷新字体缓存
fc-cache -fv
```

#### PDF 报告生成依赖

```bash
# WeasyPrint 依赖（用于生成验证报告 PDF）
apt install -y \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info

pip install weasyprint
```

#### 网页截图依赖

```bash
# Playwright 浏览器
pip install playwright
playwright install chromium
playwright install-deps chromium
```

#### 一键安装脚本

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
    fonts-wqy-microhei \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 && \
fc-cache -fv && \
pip install aiohttp playwright weasyprint && \
playwright install chromium && \
playwright install-deps chromium
"
```

## 新闻验证功能详解

### 验证流程

1. **事实提取**：从新闻文本中识别可验证的事实点
   - 时间、地点、人物、数字、事件、引用
   - 按可验证性分级（高/中/低）

2. **来源评估**：评估搜索结果的可信度
   - 静态评估：基于预定义的白名单/黑名单
   - 动态评估：检查 HTTPS、域名年龄、ICP 备案

3. **综合验证**：计算新闻可信度评分
   - 来源可信度权重（默认 40%）
   - 一致性评分权重（默认 40%）
   - 语言客观性权重（默认 20%）

4. **生成报告**：输出验证结论和 PDF 报告

### 可信度等级

| 等级 | 分数范围 | 说明 |
|------|----------|------|
| 高可信度 | 80-100 | 官方媒体、权威机构、知名国际媒体 |
| 中等可信度 | 50-79 | 地方媒体、行业媒体、门户网站 |
| 低可信度 | 0-49 | 自媒体、论坛、未知来源 |

### 验证结论类型

| 结论 | 条件 | 说明 |
|------|------|------|
| 真实 | 评分 >= 80 | 多个权威来源证实 |
| 部分真实 | 评分 60-79 | 部分内容可证实 |
| 无法验证 | 评分 40-59 | 缺乏足够证据 |
| 可能虚假 | 评分 < 40 | 与权威来源矛盾 |

### 来源白名单示例

```python
# 高可信度来源（80-100分）
- 新华网、人民网、央视网
- 政府官网（*.gov.cn）
- 知名国际媒体（BBC、Reuters、AP）

# 中等可信度来源（50-79分）
- 地方媒体、行业媒体
- 门户网站新闻频道
- 知名科技媒体

# 低可信度来源（0-49分）
- 自媒体平台
- 论坛、贴吧
- 未知来源
```

## 安全机制

### 1. 路径沙箱

- 所有文件操作限制在用户工作区内
- 防止路径遍历攻击（如 `../../../etc/passwd`）
- 符号链接检查，防止链接指向工作区外
- 严格的前缀检查，避免边界情况绕过

### 2. 命令过滤

**白名单命令：**
- 文档转换：pandoc, libreoffice, soffice
- 图像处理：convert, magick (ImageMagick)
- 音视频：ffmpeg, ffprobe
- PDF 处理：pdftotext, pdfinfo, pdftoppm, pdfimages
- 压缩解压：zip, unzip, tar
- 电子书：ebook-convert, ebook-meta
- 只读命令：cat, head, tail, wc, file

**黑名单命令（绝对禁止）：**
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

## 配置选项

在 AstrBot 配置中可设置：

```yaml
plugins:
  workspace:
    # ===== 权限配置 =====
    enable_whitelist: true          # 是否启用用户白名单
    whitelist_users: ""             # 白名单用户列表（逗号分隔）
    admin_users: ""                 # 管理员用户列表（逗号分隔）

    # ===== 存储配置 =====
    user_quota_mb: 100              # 用户存储配额（MB）
    max_read_lines: 500             # 单次最大读取行数
    max_send_file_size_mb: 50       # 最大发送文件大小（MB）
    auto_save_uploaded_files: true  # 自动保存上传文件
    command_timeout: 60             # 命令默认超时（秒）
    extra_whitelist_commands: ""    # 额外允许的命令（逗号分隔）

    # ===== 多 Agent 配置 =====
    enable_multi_agent: false       # 启用多 Agent 模式
    sub_agent_provider_id: ""       # 子 Agent 模型提供商
    enable_code_analyzer: true      # 启用代码分析代理
    enable_task_planner: true       # 启用任务规划代理
    code_analyzer_provider_id: ""   # 代码分析代理模型
    task_planner_provider_id: ""    # 任务规划代理模型

    # ===== 新闻验证配置 =====
    enable_fact_checker: true       # 启用新闻验证代理
    fact_checker_provider_id: ""    # 新闻验证代理模型
    max_search_results: 10          # 最大搜索结果数量
    enable_dynamic_check: true      # 启用动态可信度检查

    # 评分权重（总和应为 1.0）
    source_weight: 0.4              # 来源可信度权重
    consistency_weight: 0.4         # 一致性评分权重
    language_weight: 0.2            # 语言客观性权重

    # ===== 截图配置 =====
    enable_screenshots: true        # 启用网页截图
    max_screenshots: 3              # 单次最大截图数量
    screenshot_timeout: 30          # 截图超时（秒）
    urlscan_api_key: ""             # urlscan.io API Key（备用方案）
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

### 新闻验证

```
用户：帮我验证这条新闻是否真实：[新闻内容]
助手：正在分析新闻内容...

提取到 5 个可验证事实点
- 时间：2024年11月30日
- 地点：北京
- 人物：某部门发言人
...

验证结论：部分真实（评分 72/100）
- 时间地点信息可证实
- 部分数据与官方来源一致
- 建议参考官方渠道确认

报告已保存: outputs/reports/verification_20241130.pdf
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

### PDF 报告生成失败

1. 确认已安装 WeasyPrint 及其依赖
2. 检查中文字体是否正确安装
3. 查看日志中的具体错误信息

### 网页截图失败

1. 确认已安装 Playwright 和 Chromium
2. 运行 `playwright install-deps chromium` 安装系统依赖
3. 检查目标网页是否可访问
4. 配置 urlscan.io API Key 作为备用方案

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

5. **网页截图**
   - 风险：访问恶意网页可能触发浏览器漏洞
   - 缓解：使用 headless 模式，禁用 JavaScript 执行危险操作
   - 建议：保持 Playwright/Chromium 更新

### 安全建议

1. **定期更新**：保持所有依赖工具更新到最新版本
2. **资源限制**：为 Docker 容器设置 CPU 和内存限制
3. **日志监控**：定期检查日志中的异常操作
4. **备份数据**：定期备份重要数据
5. **权限控制**：使用白名单限制可使用插件的用户

## 许可证

MIT License

## 更新日志

### v2.1.0
- 新增新闻验证功能
  - 事实提取器：自动识别可验证事实点
  - 来源评估：白名单/黑名单 + 动态检查
  - PDF 报告生成：支持中文
  - 网页截图：Playwright + urlscan.io 备用
- 新增可信度评估模块
- 新增并行 Agent 调度器
- 代码规范化（ruff）

### v2.0.0
- 多用户隔离工作区
- 安全沙箱机制
- 命令白名单/黑名单
- 存储配额管理
- 新增 convert_office 工具
- 优化提示词，简化回复格式
- 定时清理功能

### v1.0.0
- 初始版本
- 基础文件操作
- 命令执行
- 文件发送
