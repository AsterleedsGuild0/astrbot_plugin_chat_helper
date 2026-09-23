"""
AstrBot 聊天助手插件 - 智能对话分析与建议

功能特性:
- 实时分析对话对象的消息意图、情绪和风险
- 提供概率评估和回应策略建议
- 支持群聊和私聊场景
- 群聊/用户独立白名单/黑名单监控
- 4个独立分析维度开关
- 冷却机制防止 LLM 过度调用
- 支持回复模式和私聊模式
- 超管/普通用户分权控制
- 按群-用户维度细粒度权限管理

灵感来源: 网络流传的"Jev"AI 对话分析助手概念图
"""

import time
from collections import defaultdict, deque
from datetime import datetime
from typing import Optional

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star

# ==================== 常量 ====================

VERSION = "1.0.0"

# 内置系统提示词
SYSTEM_PROMPT_TEMPLATE = """你是一位专业的对话分析专家，擅长解读中文社交语境下对话中的隐含意图、情绪状态和潜在风险。

你的任务：分析对话中 **对方** 的消息，帮助用户理解对方的真实意图，并给出恰当的回应建议。

## 核心原则
1. 基于完整上下文分析，不要孤立看待单条消息
2. 概率评估要有依据，不要凭空猜测
3. 回应建议要具体可行，不要泛泛而谈
4. 注意中文社交语境：反讽、暗示、试探、撒娇、欲擒故纵等复杂表达
5. 关注"话中有话"——很多话表面意思和真实意图往往不同
6. 保持客观中立，不过度解读也不低估风险

## 分析维度
{dimensions}

## 输出格式
- 使用清晰分段和 emoji 增强可读性
- 每个维度 1-3 句话，简洁有力
- 概率用百分比（如 72%）
- 风险等级用 X/10 格式
- 不确定时标注"存疑"
- 全部使用中文

## 约束
- 分析仅供参考，不能替代真实沟通
- 不鼓励欺骗、操控或不健康的关系行为
- 检测到严重危险信号（威胁、自残等）时明确提醒用户
"""

# 各维度提示词片段
DIMENSION_PROMPTS = {
    "intent": """### 📊 意图解读
- 表面含义：对方字面在说什么
- 真实意图：对方真正想表达/获得什么（附概率）
- 其他可能：其他合理解读（附概率）""",
    "emotion": """### ❤️ 情绪评估
- 当前情绪状态（如平静、期待、不满、撒娇、生气、焦虑等）
- 情绪强度（1-10）
- 趋势判断（上升 / 稳定 / 下降）""",
    "danger": """### ⚠️ 风险等级 X/10
- 风险类型（情感风险 / 沟通风险 / 关系风险等）
- 简要说明
- 风险等级 >= 7 时标注 "🚨 紧急提醒" """,
    "action": """### 💡 回应建议
- 2-3 个推荐回应策略，附推荐度百分比
- 应该避免的回应方式
- 情况紧急时建议"立即停止，不要画蛇添足" """,
}

# 分析模式对应的指令
MODE_INSTRUCTIONS = {
    "quick": "请简要分析，每个维度 1 句话，重点看意图和风险。",
    "standard": "请标准分析，每个维度 2-3 句话，包含概率评估。",
    "detailed": "请详细分析，深入解读每个维度，给出全面概率评估和多层建议。",
}


# ==================== 权限辅助 ====================


def _parse_permission_list(config: AstrBotConfig, key: str) -> list[dict]:
    """从配置解析 template_list 为 dict 列表。"""
    raw = config.get(key, [])
    if isinstance(raw, list):
        return raw
    return []


def _is_admin(sender_id: str, admin_users: set) -> bool:
    """判断是否为超管。"""
    return sender_id in admin_users


def _check_entry_permission(
    entries: list[dict], group_id: str, sender_id: str
) -> bool:
    """
    检查 sender_id 是否对 group_id 有命令设置权限。
    匹配规则：条目 (group_id, user_id) 与请求匹配，且 can_set=True。
    """
    for entry in entries:
        entry_group = entry.get("group_id", "")
        entry_user = entry.get("user_id", "")
        can_set = entry.get("can_set", False)
        # group_id 为空表示全局
        if entry_group and entry_group != group_id:
            continue
        if entry_user and entry_user != sender_id:
            continue
        if can_set:
            return True
    return False


def _get_group_mode(entries: list[dict], group_id: str) -> str | None:
    """获取指定群的自定义分析模式，未设置返回 None。"""
    for entry in entries:
        if entry.get("group_id") == group_id:
            mode = entry.get("mode", "")
            if mode in MODE_INSTRUCTIONS:
                return mode
    return None


# ==================== 插件主类 ====================


class ChatHelperPlugin(Star):
    """
    AstrBot 聊天助手插件

    监听群聊/私聊消息，调用 LLM 分析对方的意图、情绪和风险，
    并提供回应建议。支持白名单/黑名单过滤和丰富的配置选项。
    """

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self._reload_config()

        # -------- 内部状态 --------
        self._buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        self._last_analysis: dict[str, float] = defaultdict(float)
        self._analysis_count: int = 0
        self._error_count: int = 0
        # 运行时添加的被分析用户 {group_id: set(user_ids)}
        self._runtime_analysis_users: dict[str, set] = defaultdict(set)
        # 运行时修改的群分析模式 {group_id: mode}
        self._runtime_group_modes: dict[str, str] = {}

        logger.info(
            f"[ChatHelper] v{VERSION} 加载完成 | "
            f"启用={self.enabled} 群监控={self.monitor_groups_mode} "
            f"用户监控={self.monitor_users_mode} "
            f"分析={self.default_analysis_mode} 冷却={self.cooldown_seconds}s"
        )

    # ================================================================
    #  配置加载
    # ================================================================

    def _reload_config(self):
        """从 self.config 重新加载所有配置。"""
        # 基础
        self.enabled: bool = self.config.get("enabled", True)
        self.provider_id: str = self.config.get("provider_id", "")
        self.default_analysis_mode: str = self.config.get("analysis_mode", "standard")

        # 监控范围
        self.monitor_groups_mode: str = self.config.get("monitor_groups_mode", "whitelist")
        self.monitored_groups: set = set(self.config.get("monitored_groups", []))
        self.monitor_users_mode: str = self.config.get("monitor_users_mode", "whitelist")
        self.monitored_users: set = set(self.config.get("monitored_users", []))

        # 超管
        self.admin_users: set = set(self.config.get("admin_users", []))

        # 被分析用户配置（群-用户维度）
        self.analysis_users: list[dict] = _parse_permission_list(
            self.config, "analysis_users"
        )
        # 分析模式配置（群维度）
        self.analysis_mode_groups: list[dict] = _parse_permission_list(
            self.config, "analysis_mode_groups"
        )

        # 权限
        self.permission_status: str = self.config.get("permission_status", "admin")
        self.permission_stats: str = self.config.get("permission_stats", "admin")

        # 分析维度
        self.enable_intent: bool = self.config.get("enable_intent_analysis", True)
        self.enable_emotion: bool = self.config.get("enable_emotion_detection", True)
        self.enable_danger: bool = self.config.get("enable_danger_assessment", True)
        self.enable_action: bool = self.config.get("enable_action_advice", True)
        self.danger_threshold: int = self.config.get("danger_threshold", 7)
        self.context_count: int = max(
            1, min(50, self.config.get("context_message_count", 10))
        )

        # 分析参数
        self.response_mode: str = self.config.get("response_mode", "reply")
        self.cooldown_seconds: int = max(5, self.config.get("cooldown_seconds", 30))

        # 高级
        self.custom_prompt: str = self.config.get("custom_system_prompt", "")

    # ================================================================
    #  配置持久化（将运行时修改同步回配置文件，供 WebUI 查看）
    # ================================================================

    def _sync_config(self):
        """将运行时状态写回 AstrBotConfig 并保存。"""
        try:
            # 合并运行时添加的被分析用户到 analysis_users
            for group_id, user_ids in self._runtime_analysis_users.items():
                for uid in user_ids:
                    # 检查是否已存在
                    exists = any(
                        e.get("group_id", "") == group_id and e.get("user_id") == uid
                        for e in self.analysis_users
                    )
                    if not exists:
                        self.analysis_users.append(
                            {"group_id": group_id, "user_id": uid, "can_set": False}
                        )

            self.config["analysis_users"] = self.analysis_users
            self.config.save_config()
        except Exception as e:
            logger.warning(f"[ChatHelper] 配置同步失败: {e}")

    # ================================================================
    #  权限判断
    # ================================================================

    def _can_use_status(self, sender_id: str) -> bool:
        """是否有查询状态权限。"""
        if self.permission_status == "anyone":
            return True
        return _is_admin(sender_id, self.admin_users)

    def _can_use_stats(self, sender_id: str) -> bool:
        """是否有查询统计权限。"""
        if self.permission_stats == "anyone":
            return True
        return _is_admin(sender_id, self.admin_users)

    def _can_manage_analysis_user(
        self, sender_id: str, group_id: str, target_user_id: str
    ) -> bool:
        """是否能设置被分析用户。超管或按配置允许的用户。"""
        if _is_admin(sender_id, self.admin_users):
            return True
        return _check_entry_permission(
            self.analysis_users, group_id, target_user_id
        )

    def _can_set_group_mode(self, sender_id: str, group_id: str) -> bool:
        """是否能设置本群分析模式。超管或按配置允许的群。"""
        if _is_admin(sender_id, self.admin_users):
            return True
        for entry in self.analysis_mode_groups:
            if entry.get("group_id") == group_id and entry.get("can_set", False):
                return True
        return False

    # ================================================================
    #  监控过滤
    # ================================================================

    def _should_monitor(self, sender_id: str, group_id: str, session_id: str) -> bool:
        """综合判断是否需要监控此消息。"""
        # 群聊维度
        if group_id:
            if not self._match_group_monitor(group_id, session_id):
                return False

        # 用户维度
        if not self._match_user_monitor(sender_id):
            return False

        # 被分析用户（静态配置 + 运行时添加）
        if self._is_analysis_target(sender_id, group_id):
            return True

        return False

    def _match_group_monitor(self, group_id: str, session_id: str) -> bool:
        """群聊维度过滤。"""
        if not self.monitored_groups:
            # 名单为空：whitelist=不监控，blacklist=全部监控
            return self.monitor_groups_mode == "blacklist"
        hit = group_id in self.monitored_groups or session_id in self.monitored_groups
        return hit if self.monitor_groups_mode == "whitelist" else not hit

    def _match_user_monitor(self, sender_id: str) -> bool:
        """用户维度过滤。"""
        if not self.monitored_users:
            return self.monitor_users_mode == "blacklist"
        hit = sender_id in self.monitored_users
        return hit if self.monitor_users_mode == "whitelist" else not hit

    def _is_analysis_target(self, sender_id: str, group_id: str) -> bool:
        """判断用户是否为被分析目标。"""
        # 运行时添加的
        if group_id in self._runtime_analysis_users:
            if sender_id in self._runtime_analysis_users[group_id]:
                return True
        if "" in self._runtime_analysis_users:
            if sender_id in self._runtime_analysis_users[""]:
                return True

        # 静态配置的
        for entry in self.analysis_users:
            entry_group = entry.get("group_id", "")
            entry_user = entry.get("user_id", "")
            if entry_user != sender_id:
                continue
            if not entry_group or entry_group == group_id:
                return True
        return False

    def _get_effective_analysis_mode(self, group_id: str) -> str:
        """获取指定群的有效分析模式（运行时 > 静态配置 > 全局默认）。"""
        # 运行时修改
        if group_id in self._runtime_group_modes:
            return self._runtime_group_modes[group_id]
        # 静态配置
        mode = _get_group_mode(self.analysis_mode_groups, group_id)
        if mode:
            return mode
        return self.default_analysis_mode

    # ================================================================
    #  消息监听
    # ================================================================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听全部消息，按配置过滤后调用 LLM 进行对话分析。"""
        try:
            if not self.enabled:
                return

            sender_id = event.get_sender_id()
            sender_name = event.get_sender_name()
            message_str = event.message_str.strip()
            group_id = event.message_obj.group_id or ""
            session_id = event.session_id

            if not message_str:
                return

            if self._is_self_message(event, sender_id):
                return

            if not self._should_monitor(sender_id, group_id, session_id):
                return

            now = time.time()
            if now - self._last_analysis[session_id] < self.cooldown_seconds:
                return

            self._buffers[session_id].append(
                {
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "content": message_str,
                    "timestamp": datetime.now().strftime("%H:%M"),
                    "is_self": False,
                }
            )

            # 获取该群有效的分析模式
            effective_mode = self._get_effective_analysis_mode(group_id)
            analysis = await self._call_llm(
                event, session_id, sender_name, message_str, effective_mode
            )

            if analysis:
                response = self._format_response(sender_name, message_str, analysis)

                if self.response_mode == "private":
                    success = await self._try_send_private(event, sender_id, response)
                    if not success:
                        yield event.plain_result(response)
                else:
                    yield event.plain_result(response)

                self._last_analysis[session_id] = now
                self._analysis_count += 1
                logger.info(
                    f"[ChatHelper] 分析#{self._analysis_count} | "
                    f"{session_id} <- {sender_name}"
                )

        except Exception as e:
            logger.error(f"[ChatHelper] 消息处理异常: {e}", exc_info=True)
            self._error_count += 1

    # ================================================================
    #  辅助判断
    # ================================================================

    @staticmethod
    def _is_self_message(event: AstrMessageEvent, sender_id: str) -> bool:
        """判断是否是机器人自身发出的消息"""
        try:
            self_id = getattr(event.message_obj, "self_id", None)
            if self_id and str(sender_id) == str(self_id):
                return True
        except Exception:
            pass
        return False

    # ================================================================
    #  LLM 分析
    # ================================================================

    async def _call_llm(
        self,
        event: AstrMessageEvent,
        session_id: str,
        sender_name: str,
        current_message: str,
        effective_mode: str,
    ) -> Optional[str]:
        """调用 LLM 进行对话分析，返回分析文本或 None"""
        try:
            context_snapshot = list(self._buffers[session_id])[-self.context_count :]

            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(
                context_snapshot, sender_name, current_message, effective_mode
            )
            full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

            provider_id = self.provider_id
            if not provider_id:
                try:
                    provider_id = await self.context.get_current_chat_provider_id(
                        event.unified_msg_origin
                    )
                except Exception as e:
                    logger.warning(f"[ChatHelper] 获取 LLM 提供商失败: {e}")
                    return None

            if not provider_id:
                logger.warning("[ChatHelper] 未找到可用的 LLM 提供商")
                return None

            resp = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=full_prompt,
            )

            if not resp or not resp.completion_text:
                logger.warning("[ChatHelper] LLM 返回空结果")
                return None

            return resp.completion_text.strip()

        except Exception as e:
            logger.error(f"[ChatHelper] LLM 调用异常: {e}", exc_info=True)
            self._error_count += 1
            return None

    def _build_system_prompt(self) -> str:
        """组装系统提示词（维度 + 自定义追加）"""
        dimensions = []
        if self.enable_intent:
            dimensions.append(DIMENSION_PROMPTS["intent"])
        if self.enable_emotion:
            dimensions.append(DIMENSION_PROMPTS["emotion"])
        if self.enable_danger:
            dimensions.append(DIMENSION_PROMPTS["danger"])
        if self.enable_action:
            dimensions.append(DIMENSION_PROMPTS["action"])

        if not dimensions:
            dimensions = [DIMENSION_PROMPTS["intent"]]

        prompt = SYSTEM_PROMPT_TEMPLATE.format(dimensions="\n\n".join(dimensions))

        if self.custom_prompt:
            prompt += f"\n\n## 用户自定义要求\n{self.custom_prompt}"

        return prompt

    def _build_user_prompt(
        self,
        context: list[dict],
        sender_name: str,
        current_message: str,
        effective_mode: str,
    ) -> str:
        """组装用户提示词（上下文 + 当前消息 + 分析指令）"""
        if context:
            lines = []
            for msg in context:
                tag = "我" if msg.get("is_self") else msg["sender_name"]
                lines.append(f"[{msg['timestamp']}] {tag}: {msg['content']}")
            context_text = "\n".join(lines)
        else:
            context_text = "（暂无历史记录）"

        mode_hint = MODE_INSTRUCTIONS.get(
            effective_mode, MODE_INSTRUCTIONS["standard"]
        )

        return (
            f"请分析以下对话中 **{sender_name}** 的最新消息。\n\n"
            f"## 对话记录\n{context_text}\n\n"
            f"## 待分析消息\n"
            f"【{sender_name}】: {current_message}\n\n"
            f"## 分析要求\n{mode_hint}\n\n"
            f"请基于对话上下文进行分析，注意对话的连贯性和隐含意义。"
        )

    # ================================================================
    #  响应格式化与发送
    # ================================================================

    @staticmethod
    def _format_response(sender_name: str, message: str, analysis: str) -> str:
        """将 LLM 分析结果包装为用户可读的响应"""
        display_msg = message[:60] + ("..." if len(message) > 60 else "")
        header = f"💬 分析 [{sender_name}] 的消息:\n「{display_msg}」\n"
        separator = "─" * 20 + "\n"
        return header + separator + analysis

    async def _try_send_private(
        self, event: AstrMessageEvent, target_id: str, text: str
    ) -> bool:
        """尝试私聊发送，成功返回 True"""
        try:
            await event.send_private_message(target_id, text)
            return True
        except Exception as e:
            logger.warning(f"[ChatHelper] 私聊发送失败，将回退到会话内回复: {e}")
            return False

    # ================================================================
    #  指令
    # ================================================================

    @filter.command_group("chat_helper")
    def chat_helper_cmd(self):
        """聊天助手指令组"""
        pass

    @chat_helper_cmd.command("status")
    async def cmd_status(self, event: AstrMessageEvent):
        """查看插件运行状态"""
        sender_id = event.get_sender_id()
        if not self._can_use_status(sender_id):
            return  # 无权限时静默

        mode = self._get_effective_analysis_mode(event.message_obj.group_id or "")
        lines = [
            f"[ChatHelper] 状态 v{VERSION}",
            f"启用: {'是' if self.enabled else '否'}",
            f"群监控: {self.monitor_groups_mode} ({len(self.monitored_groups)})",
            f"用户监控: {self.monitor_users_mode} ({len(self.monitored_users)})",
            f"分析模式: {mode} (本群)",
            f"冷却时间: {self.cooldown_seconds}s",
            f"回复模式: {self.response_mode}",
        ]
        yield event.plain_result("\n".join(lines))

    @chat_helper_cmd.command("stats")
    async def cmd_stats(self, event: AstrMessageEvent):
        """查看分析统计和配置概览"""
        sender_id = event.get_sender_id()
        if not self._can_use_stats(sender_id):
            return

        mode = self._get_effective_analysis_mode(event.message_obj.group_id or "")
        lines = [
            f"[ChatHelper] 统计 v{VERSION}",
            f"已分析: {self._analysis_count} 次",
            f"错误: {self._error_count} 次",
            "",
            "[配置概览]",
            f"群名单: {len(self.monitored_groups)}",
            f"用户名单: {len(self.monitored_users)}",
            f"被分析用户: {len(self.analysis_users)}",
            f"群模式配置: {len(self.analysis_mode_groups)}",
            "",
            "[分析维度]",
            f"意图: {'开' if self.enable_intent else '关'}",
            f"情绪: {'开' if self.enable_emotion else '关'}",
            f"风险: {'开' if self.enable_danger else '关'}",
            f"建议: {'开' if self.enable_action else '关'}",
            f"当前群模式: {mode}",
        ]
        yield event.plain_result("\n".join(lines))

    @chat_helper_cmd.command("mode")
    async def cmd_mode(self, event: AstrMessageEvent, mode: str = ""):
        """切换本群分析模式（超管或已授权群成员）"""
        sender_id = event.get_sender_id()
        group_id = event.message_obj.group_id or ""

        if not group_id:
            yield event.plain_result("[ChatHelper] 此命令仅在群聊中可用")
            return

        if not self._can_set_group_mode(sender_id, group_id):
            return  # 无权限时静默

        if mode in MODE_INSTRUCTIONS:
            self._runtime_group_modes[group_id] = mode
            yield event.plain_result(f"[ChatHelper] 本群分析模式已切换为: {mode}")
        else:
            current = self._get_effective_analysis_mode(group_id)
            available = " / ".join(MODE_INSTRUCTIONS.keys())
            yield event.plain_result(
                f"[ChatHelper] 用法: /chat_helper mode <模式>\n"
                f"可用: {available}\n"
                f"当前: {current}"
            )

    @chat_helper_cmd.command("analyze")
    async def cmd_analyze(self, event: AstrMessageEvent, user_id: str = "", action: str = ""):
        """设置被分析用户（添加/移除），修改会自动同步到 WebUI 配置"""
        sender_id = event.get_sender_id()
        group_id = event.message_obj.group_id or ""

        if not user_id:
            yield event.plain_result(
                "[ChatHelper] 用法: /chat_helper analyze <用户ID> <add|remove>\n"
                "在目标群内使用，留空群组ID则全局生效"
            )
            return

        if not self._can_manage_analysis_user(sender_id, group_id, user_id):
            return  # 无权限时静默

        if action == "add":
            self._runtime_analysis_users[group_id].add(user_id)
            self._sync_config()
            yield event.plain_result(f"[ChatHelper] 已将 {user_id} 加入本群被分析用户")
        elif action == "remove":
            self._runtime_analysis_users[group_id].discard(user_id)
            # 从配置中也移除
            self.analysis_users[:] = [
                e
                for e in self.analysis_users
                if not (e.get("group_id", "") == group_id and e.get("user_id") == user_id)
            ]
            self._sync_config()
            yield event.plain_result(f"[ChatHelper] 已将 {user_id} 从本群被分析用户移除")
        else:
            current = "在列表中" if self._is_analysis_target(user_id, group_id) else "不在列表中"
            yield event.plain_result(
                f"[ChatHelper] 用户 {user_id} 当前{current}\n"
                f"用法: /chat_helper analyze {user_id} <add|remove>"
            )

    # ================================================================
    #  生命周期
    # ================================================================

    async def terminate(self):
        """插件卸载时清理资源"""
        self._buffers.clear()
        self._last_analysis.clear()
        self._runtime_analysis_users.clear()
        self._runtime_group_modes.clear()
        logger.info("[ChatHelper] 插件已卸载")
