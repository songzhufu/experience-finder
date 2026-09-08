# Xiaohongshu Interview Research

一个面向小红书公开面经的本地采集与整理工具。它通过 Playwright 连接可见 Chrome，由用户完成登录、验证和详情页点击；脚本只提取当前可见的笔记内容并输出结构化 Markdown。

## 功能

- 按公司、岗位或关键词打开小红书搜索页
- 支持“最新”排序下的人工点击协作采集
- 提取标题、发布时间、原文链接和正文
- 保存本地 JSON/JSONL 缓存，按 URL 去重
- 按发布时间倒序生成 Markdown 或 TXT 报告
- 支持单篇采集和多篇连续协作采集
- 提供离线 smoke test，不依赖小红书登录

## 使用边界

本项目不绕过登录、验证码、滑块或平台风控。遇到验证页面时，请在可见 Chrome 中手动完成操作。请遵守平台规则，仅处理用户主动打开的公开页面，并避免采集不必要的个人信息。

## 本地部署

### 1. 准备环境

需要 Python 3.10+、Google Chrome 和 PowerShell。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m playwright install chromium
```

如果 PowerShell 阻止激活虚拟环境，可以仅在当前终端执行：

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### 2. 打开可见 Chrome

```powershell
powershell -ExecutionPolicy Bypass -File scripts\open_visible_chrome.ps1 -Port 9222
```

在打开的 Chrome 中登录小红书。该浏览器使用项目内的独立配置目录，不会改动你日常浏览器的默认用户配置。

### 3. 采集单篇面经

运行下面命令后，脚本会打开搜索结果页。手动点击一篇目标笔记，脚本将自动保存 JSON 与 Markdown。

```powershell
.\.venv\Scripts\python.exe scripts\manual_detail_collect.py \
  --keyword "字节跳动 Agent 开发 面经" \
  --json-output data\manual_detail_note.json \
  --markdown-output output\manual_detail_note.md \
  --cdp-url http://127.0.0.1:9222
```

### 4. 连续协作采集

该模式会在每篇成功采集后自动返回下一组“最新”搜索结果，继续等待人工点击。

```powershell
.\.venv\Scripts\python.exe scripts\interactive_click_batch.py \
  --target 100 \
  --cdp-url http://127.0.0.1:9222 \
  --raw-output data\byte_agent_clicks_raw.jsonl \
  --markdown-output output\byte_agent_interviews_recent.md
```

### 5. 离线自测

```powershell
.\.venv\Scripts\python.exe scripts\run_offline_test.py
```

## 输出格式

每篇帖子在最终 Markdown 中使用一级标题，发布时间和正文使用二级标题；原文链接以普通文本放在发布时间下方。

```markdown
# 帖子标题

## 发布时间

2026-02-20

https://www.xiaohongshu.com/explore/example

## 面经内容

正文内容……
```

## GitHub 同步

初始化并首次推送到 GitHub 前，请先在 GitHub 创建一个空仓库，然后执行：

```powershell
git init
git add README.md .gitignore requirements.txt config.example.json SKILL.md scripts references agents
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

.gitignore 已排除浏览器配置、登录状态、采集数据和生成报告，避免把会话数据或个人采集内容上传到远程仓库。
