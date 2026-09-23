# 更新日志

## 1.0.1 (2026-09-23)

### 🧹 日常维护

- 更新 CHANGELOG @github-actions[bot]

### 其他变更

- v1.0.1 @azmiao

## 1.0.0 (2026-09-23)

### ✨ 新功能

- 重构CHANGLOG生成逻辑 @azmiao
- 对话分析结果改用 HTML 图片渲染，修复 template_list 配置格式 @azmiao
- 添加插件图标与中文显示名「聊天对话分析助手」 @azmiao
- 新增模板渲染模块，统一现代化卡片样式输出 @azmiao
- 实现智能聊天助手插件核心功能 @azmiao

### 🐛 Bug 修复

- 禁止 branch push 触发 release workflow，避免 changelog commit 产生竞争 @azmiao
- 发布前删除残留 release，避免 tag 重打导致 422 冲突 @azmiao
- release 发布时覆盖已有文件，避免 tag 重打导致冲突 @azmiao
- release artifact 同时上传 zip 文件，修复发布时找不到包 @azmiao
- 修复旧版无效 extract 子命令 @azmiao
- 修复Ruff校验 @azmiao
- 修复 release 版本校验时 v 前缀不一致导致的比较失败 @azmiao
- 修复 html_render 调用方式，直接传模板字符串和数据而非自行渲染 @azmiao
- 转义 SYSTEM_PROMPT_TEMPLATE 中的 JSON 花括号，修复 KeyError @azmiao
- 清理残留的 render_card 调用，修复 NameError @azmiao
- 修复 template_list 配置格式导致 WebUI 无法识别 @azmiao
- 合并 templates.py 到 main.py，修复 AstrBot 插件加载 ModuleNotFoundError @azmiao
- 修复 generate_changelog.py import 排序问题 @azmiao

### 🎨 代码重构

- 合并 build 和 release workflow，统一为 Build & Release @azmiao
- 重写 release workflow，简化结构并修复 zip 嵌套 @azmiao
- 优化权限配置和命令交互 @azmiao
- 重构权限体系与配置结构 @azmiao

### 📚 文档

- 补充说明灵感来源为 Jev 聊天助手 @azmiao
- 更新 README，移除超管指令和 tests 引用，更新效果示例说明 @azmiao
- 补充完整 README 使用文档 @azmiao

### 🧪 测试

- 添加 VSCode 启动配置和单元测试 @azmiao

### ⚙️ 持续集成

- 修复 artifact 嵌套 zip，上传解压后的插件目录 @azmiao
- 修复 artifact 嵌套 zip 问题，上传前将包移到根目录 @azmiao
- build workflow 改为 push 触发，release 保持 tag 触发 @azmiao
- 拆分手动打包为独立 workflow @azmiao
- 添加手动触发仅打包工作流 @azmiao

### 🧹 日常维护

- 更新 CHANGELOG @github-actions[bot]
- 更新 CHANGELOG @github-actions[bot]
- 更新 CHANGELOG @github-actions[bot]
- 更新 CHANGELOG @github-actions[bot]
- 更新 CHANGELOG @github-actions[bot]
- 重构 release workflow，支持自动生成 CHANGELOG 并提交 @azmiao
- 调整分析卡片样式，缩小背景留白并改为浅色背景 @azmiao
- 调整VScode配置 @azmiao
- 优化CHANGELOG生成逻辑 @azmiao
- 移除 tests 目录并停止 git 跟踪 @azmiao
- 添加 CI/CD 自动化发布基础设施 @azmiao

### 其他变更

- Initial commit @azmiao
