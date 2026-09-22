# astrbot_plugin_chat_helper

AstrBot 智能聊天助手插件 — 实时分析对话中对方的意图、情绪与风险等级，提供概率评估与回应建议。

灵感来源于网络上流传的 "Jev" AI 对话分析助手概念图，将其从一个段子变成了可实际使用的 AstrBot 插件。

当前版本：`v1.0.0`

---

## 安装

### 前置要求

- AstrBot `>= 4.0.0`
- 一个已配置的 LLM 提供商（如 OpenAI、DeepSeek、Gemini 等）

### 安装方式

1. 将本插件放入 AstrBot 插件目录：
   ```
   data/plugins/astrbot_plugin_chat_helper/
   ```
2. 重启 AstrBot，或在 WebUI 插件管理页面点击重载。
3. 在 WebUI 的插件配置页完成基础配置（见下方 [配置指南](#配置指南)）。

---

## 效果示例

当女友发来 "你今天是不是又忘了我跟你说过什么？"：

```
💬 分析 [宝儿] 的消息:
「你今天是不是又忘了我跟你说过什么？」
────────────────────
📊 意图解读
表面：询问你是否还记得某事（7%）
真实：想确认你在不在乎她（72%）| 生气想吵架（20%）

❤️ 情绪评估
不满+期待，强度 7/10，趋势上升

⚠️ 风险等级 9/10
🚨 紧急提醒——这是典型的"送命题"，空口回答极易踩雷

💡 回应建议
- 先别急着答具体内容，表示"记得，让我自己说"（推荐度 91%）
- 立刻道歉并承诺补偿（推荐度 65%）
- 避免：硬猜答案（4% 成功率）
```

---

## 指令

| 指令 | 说明 |
|------|------|
| `/chat_helper status` | 查看插件运行状态、分析统计和配置概览 |
| `/chat_helper on` | 启用插件 |
| `/chat_helper off` | 禁用插件 |
| `/chat_helper mode quick` | 切换为简要分析模式 |
| `/chat_helper mode standard` | 切换为标准分析模式 |
| `/chat_helper mode detailed` | 切换为详细分析模式 |

---

## 配置指南

所有配置均在 AstrBot WebUI 的插件配置页面完成，无需修改代码。

### 基础设置

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | 开关 | `true` | 总开关，关闭后停止所有监控与分析 |
| `provider_id` | 下拉选择 | 空（自动） | 指定 LLM 服务商，留空则使用当前会话默认的 |

### 监控范围

通过监控模式 + 名单的组合，可以精确控制哪些消息会被分析：

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `monitor_mode` | 下拉 | `whitelist` | `whitelist`=只监控名单内的群/人；`blacklist`=排除名单内的；`all`=监控全部 |
| `monitored_groups` | 列表 | `[]` | 群组ID 或完整会话ID（在目标群内发送 `/sid` 获取） |
| `monitored_users` | 列表 | `[]` | 用户ID，可单独指定某个人 |
| `excluded_users` | 列表 | `[]` | 排除列表，命中后**永远不会被分析**，优先级最高 |

**常见场景配置：**

| 场景 | monitor_mode | monitored_groups | monitored_users |
|------|-------------|-----------------|-----------------|
| 只分析某个群 | `whitelist` | `["群号"]` | 留空 |
| 只分析某个人（含私聊+群聊） | `whitelist` | 留空 | `["用户QQ号"]` |
| 分析所有群和私聊 | `all` | — | — |
| 排除某个群 | `blacklist` | `["群号"]` | 留空 |

### 分析维度

4 个维度均可独立开关，可根据需求自由组合：

| 配置项 | 默认值 | 分析内容 |
|--------|--------|---------|
| `enable_intent_analysis` | `true` | 表面含义 vs 真实意图，附概率评估 |
| `enable_emotion_detection` | `true` | 当前情绪状态、强度(1-10)、趋势 |
| `enable_danger_assessment` | `true` | 风险等级(1-10) + 类型 + 紧急提醒 |
| `enable_action_advice` | `true` | 推荐回应策略 + 成功率 + 避雷建议 |

### 分析参数

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `analysis_mode` | 下拉 | `standard` | `quick`=一句话简要；`standard`=标准概率分析；`detailed`=深度详细 |
| `danger_threshold` | 整数 | `7` | 风险达到此值时触发紧急提醒（建议 6-8） |
| `context_message_count` | 整数 | `10` | 分析时参考的历史消息条数（1-50） |

### 回复控制

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `response_mode` | 下拉 | `reply` | `reply`=在原会话中回复；`private`=私聊发给触发者（更隐蔽） |
| `cooldown_seconds` | 整数 | `30` | 同一会话两次分析的最小间隔，防止 LLM 疯狂调用 |

### 高级定制

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `custom_system_prompt` | 多行文本 | 空 | 自定义分析提示词，追加到内置提示词之后，可定制分析风格/语气 |

**自定义提示词示例：**

```
你是一个恋爱关系顾问，特别关注亲密关系中的沟通模式。
分析时请考虑双方的情感投入程度和关系阶段。
对于"送命题"类的对话，请给出特别详细的求生建议。
```

---

## 支持的聊天平台

本插件基于 AstrBot 的统一消息事件接口开发，理论上支持所有 AstrBot 适配的消息平台，包括但不限于：

- QQ（OneBot / QQ 官方）
- Telegram
- Discord
- 飞书（Lark）
- 钉钉
- Slack
- LINE
- Matrix
- 企业微信

> 具体兼容性取决于当前 AstrBot 部署的消息适配器。

---

## 工作原理

```
用户发送消息
    │
    ▼
[过滤] 启用？非自己？在监控范围？冷却过了？
    │
    ▼
[缓冲] 将消息存入会话缓冲区（最近 N 条）
    │
    ▼
[LLM] 组装提示词（系统提示词 + 上下文 + 当前消息 + 分析指令）
    │
    ▼
[输出] 格式化分析结果并发送
    │
    ▼
[模式] reply → 发送到当前会话
        private → 私聊发给触发者
```

---

## 开发与发布

### 本地开发

```bash
# 安装依赖（仅开发工具链需要，插件运行无额外依赖）
uv sync

# 运行测试
uv run python -m unittest discover -s tests -v

# 打包测试版本
uv run python scripts/package_plugin.py --dev-version

# 打包正式发布版
uv run python scripts/package_plugin.py
```

### 发布流程

1. 更新 `metadata.yaml` 中的版本号
2. 更新 `CHANGELOG.md` 中的版本记录
3. 推送 tag：

```bash
git tag v1.0.1
git push origin v1.0.1
```

4. GitHub Actions 自动验证版本号、提取 release notes、打包并发布 GitHub Release

---

## 项目结构

```
astrbot_plugin_chat_helper/
├── main.py                  # 插件主逻辑
├── metadata.yaml            # AstrBot 插件元数据
├── _conf_schema.json        # WebUI 配置面板 Schema
├── CHANGELOG.md             # 版本变更记录
├── LICENSE                  # MIT 许可证
├── pyproject.toml           # 项目配置（uv 管理）
├── requirements.txt         # 运行时依赖（无额外依赖）
├── scripts/
│   ├── package_plugin.py    # 打包脚本
│   └── generate_changelog.py # Changelog 生成/提取
├── tests/
│   ├── astrbot_stubs.py     # AstrBot API 桩模块
│   ├── test_package_plugin.py
│   └── test_generate_changelog.py
└── .github/workflows/
    └── release.yml          # GitHub Actions 发布流水线
```

---

## 常见问题

### 为什么某些消息没有被分析？

请检查：
1. 插件是否已启用（`enabled=true` 或发送 `/chat_helper on`）
2. 监控模式配置是否正确（默认 `whitelist` 需要名单中有匹配项）
3. 该会话是否还在冷却时间内（默认 30 秒）
4. 发送者是否在排除列表中

### 如何获取群组/用户的完整会话 ID？

在目标群组中发送 `/sid`，AstrBot 会回复当前会话的完整 ID，复制粘贴到配置中即可。

### LLM 调用失败怎么办？

请确认：
1. AstrBot 已正确配置至少一个 LLM 提供商
2. 插件配置中 `provider_id` 留空或指向有效的服务商
3. LLM 服务商的 API Key 有效且有足够额度

### 如何减少 Token 消耗？

- 设置 `analysis_mode=quick`（更简短的提示词）
- 降低 `context_message_count`（参考更少的历史消息）
- 增大 `cooldown_seconds`（降低分析频率）
- 使用 `whitelist` 模式只监控特定群/人

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。

## 致谢

- 灵感来源于网络上流传的 "Jev" AI 对话分析助手概念图
- CI/CD 参考了 [astrbot_plugin_xqa](https://github.com/AsterleedsGuild0/astrbot_plugin_xqa) 的发布流水线设计
