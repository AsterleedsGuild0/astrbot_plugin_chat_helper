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

### 用户指令（按权限开放）

| 指令 | 说明 | 权限要求 |
|------|------|---------|
| `/chat_helper status` | 查看插件运行状态 | 超管 或 配置为所有人可用 |
| `/chat_helper stats` | 查看分析统计和配置概览 | 超管 或 配置为所有人可用 |
| `/chat_helper mode <模式>` | 切换本群分析模式 | 超管 或 已授权群成员 |
| `/chat_helper analyze <用户ID> <add\|remove>` | 设置被分析用户 | 超管 或 已授权用户 |

### 超管指令

| 指令 | 说明 |
|------|------|
| `/chat_helper on` | 启用插件 |
| `/chat_helper off` | 禁用插件 |

> **无权限时静默**——非授权用户发送命令不会收到任何响应。

---

## 配置指南

所有配置均在 AstrBot WebUI 的插件配置页面完成。

### 0. 基础

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | 开关 | `true` | 总开关，关闭后停止所有监控与分析 |
| `provider_id` | 下拉选择 | 空（自动） | LLM 服务商，留空使用 AstrBot 全局默认提供商 |

### 1. 监控范围

群聊和用户**各自独立**设置白名单/黑名单模式，共同决定哪些消息会进入分析流程。

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `monitor_groups_mode` | 下拉 | `whitelist` | 群聊名单模式：`whitelist`=只监控名单内的群，`blacklist`=排除名单内的群 |
| `monitored_groups` | 列表 | `[]` | 群组ID 或完整会话ID（在目标群内发送 `/sid` 获取） |
| `monitor_users_mode` | 下拉 | `whitelist` | 用户名单模式：`whitelist`=只监控名单内的用户，`blacklist`=排除名单内的用户 |
| `monitored_users` | 列表 | `[]` | 用户ID |

**常见场景：**

| 场景 | 群聊模式 | 群聊名单 | 用户模式 | 用户名单 |
|------|---------|---------|---------|---------|
| 只监控某个群 | `whitelist` | `["群号"]` | `whitelist` | 留空 |
| 只监控某个人 | `whitelist` | 留空 | `whitelist` | `["用户ID"]` |
| 只监控某群里的某个人 | `whitelist` | `["群号"]` | `whitelist` | `["用户ID"]` |
| 排除某个群 | `blacklist` | `["群号"]` | `whitelist` | 留空 |
| 监控所有群+排除某人 | `whitelist` | 留空 | `blacklist` | `["用户ID"]` |

### 2. 基础配置（权限管理）

#### 超管

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `admin_users` | 列表 | `[]` | 超管用户ID列表，超管拥有所有命令权限 |

#### 被分析用户（按群-用户维度隔离）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `analysis_users` | 模板列表 | `[]` | 配置哪些用户的消息会被分析 |

每个条目包含：

| 字段 | 说明 |
|------|------|
| `group_id` | 群组ID，留空表示全局生效 |
| `user_id` | 被分析用户ID，该用户的消息将被自动分析 |
| `can_set` | 是否允许该用户通过命令将自己加入/移出分析列表 |

#### 分析模式（按群维度隔离）

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `analysis_mode_groups` | 模板列表 | `[]` | 为不同群设置不同的分析模式 |

每个条目包含：

| 字段 | 说明 |
|------|------|
| `group_id` | 群组ID |
| `mode` | 分析模式：`quick`/`standard`/`detailed` |
| `can_set` | 是否允许该群成员通过命令切换本群模式 |

#### 查询权限

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `permission_status` | 下拉 | `admin` | 谁可以查询运行状态：`admin`=仅超管，`anyone`=所有人 |
| `permission_stats` | 下拉 | `admin` | 谁可以查看统计概览：`admin`=仅超管，`anyone`=所有人 |

### 3. 分析参数

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `analysis_mode` | 下拉 | `standard` | 全局默认分析模式（未按群单独设置时生效） |
| `enable_intent_analysis` | 开关 | `true` | 意图解读 |
| `enable_emotion_detection` | 开关 | `true` | 情绪检测 |
| `enable_danger_assessment` | 开关 | `true` | 风险评估 |
| `enable_action_advice` | 开关 | `true` | 行动建议 |
| `danger_threshold` | 整数 | `7` | 危险警报阈值（建议 6-8） |
| `context_message_count` | 整数 | `10` | 上下文消息数（1-50） |
| `cooldown_seconds` | 整数 | `30` | 分析冷却（秒） |
| `response_mode` | 下拉 | `reply` | 回复模式：`reply`=在原会话中回复，`private`=私聊发送 |

### 4. 高级定制

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `custom_system_prompt` | 多行文本 | 空 | 自定义分析提示词，追加到内置提示词之后 |

---

## 权限体系

```
超管 (admin_users)
  ├── 所有命令权限
  ├── 可修改所有运行时配置
  └── 在 WebUI 中修改全部配置

已授权用户 (analysis_users.can_set / analysis_mode_groups.can_set)
  ├── /chat_helper analyze add/remove — 管理自己的分析状态
  └── /chat_helper mode — 切换本群分析模式

查询权限 (permission_status / permission_stats)
  ├── admin — 仅超管可用
  └── anyone — 所有用户可用

无权限用户
  └── 发送任何 /chat_helper 命令均无响应（静默）
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
[过滤] 启用？非自己？群监控通过？用户监控通过？是被分析目标？冷却过了？
    │
    ▼
[缓冲] 将消息存入会话缓冲区（最近 N 条）
    │
    ▼
[LLM] 组装提示词（系统提示词 + 上下文 + 当前消息 + 有效分析模式）
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
uv sync
uv run python -m unittest discover -s tests -v
uv run python scripts/package_plugin.py --dev-version
```

### 发布流程

1. 更新 `metadata.yaml` 中的版本号
2. 更新 `CHANGELOG.md` 中的版本记录
3. 推送 tag：`git tag v1.0.1 && git push origin v1.0.1`
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

按以下顺序排查：
1. 插件是否已启用（WebUI 中 `enabled=true` 或超管发送 `/chat_helper on`）
2. 群聊监控：该群是否在名单内（白名单）或不在名单内（黑名单）
3. 用户监控：该用户是否在名单内（白名单）或不在名单内（黑名单）
4. 该用户是否在被分析用户列表中（`analysis_users` 或运行时添加）
5. 该会话是否还在冷却时间内（默认 30 秒）

### 如何获取群组/用户的完整会话 ID？

在目标群组中发送 `/sid`，AstrBot 会回复当前会话的完整 ID，复制粘贴到配置中即可。

### LLM 调用失败怎么办？

请确认：
1. AstrBot 已正确配置至少一个 LLM 提供商
2. 插件配置中 `provider_id` 留空或指向有效的服务商
3. LLM 服务商的 API Key 有效且有足够额度

### 如何减少 Token 消耗？

- 使用 `quick` 分析模式
- 降低 `context_message_count`（如 5）
- 增大 `cooldown_seconds`（如 60）
- 精确控制 `analysis_users` 只分析需要的目标用户

---

## 许可证

MIT License — 详见 [LICENSE](LICENSE) 文件。

## 致谢

- 灵感来源于网络上流传的 "Jev" AI 对话分析助手概念图
- CI/CD 参考了 [astrbot_plugin_xqa](https://github.com/AsterleedsGuild0/astrbot_plugin_xqa) 的发布流水线设计
