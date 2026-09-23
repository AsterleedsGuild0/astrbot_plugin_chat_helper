# 更新日志

本项目的所有重要变更都将记录在此文件中。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增

- 新增 `templates.py` 内置模板模块，统一所有输出为现代化卡片样式
- LLM 分析结果支持 JSON 结构化渲染，含意图/情绪/风险/建议四维展示
- 新增 Unicode 进度条可视化（情绪强度、风险等级）
- 新增插件图标 `logo.png`（256×256，从 azmiao.png 缩放生成）
- `metadata.yaml` 新增 `display_name` 和 `short_desc` 字段，插件显示名改为「聊天对话分析助手」

### 变更

- 重构 `_format_response`，分析结果改用卡片模板渲染
- 重构 `/chat_helper status|stats|mode|analyze` 命令输出为统一卡片样式
- 优化系统提示词，引导 LLM 返回标准 JSON 格式（保留纯文本回退兼容）
- 更新 README 标题为「聊天对话分析助手」

## [v1.0.0] - 2026-09-21

### 新增

- 实现智能对话分析核心功能，监听群聊/私聊消息并调用 LLM 分析意图、情绪与风险
- 支持白名单/黑名单/全量三种监控模式，可指定群组和用户
- 4 个独立分析维度：意图解读、情绪检测、风险评估、行动建议
- 3 种分析深度模式：quick / standard / detailed
- 冷却机制防止 LLM 过度调用，支持可配置间隔
- 支持会话内回复（reply）和私聊回复（private）两种模式
- 自定义系统提示词追加能力
- 16 项 WebUI 可配置项（_conf_schema.json）
- 指令组 `/chat_helper status|on|off|mode` 用于运行时控制
- 添加 GitHub Actions 自动打包发布工作流
- 添加 changelog 自动生成与提取工具脚本
- 添加 AstrBot 插件打包脚本

[Unreleased]: https://github.com/azmiao/astrbot_plugin_chat_helper/compare/v1.0.0...HEAD
[v1.0.0]: https://github.com/azmiao/astrbot_plugin_chat_helper/releases/tag/v1.0.0
