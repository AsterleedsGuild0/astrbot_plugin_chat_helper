"""
AstrBot 聊天助手插件 - 智能对话分析与建议

功能特性:
- 实时分析对话对象的消息意图、情绪和风险
- 提供概率评估和回应策略建议
- 支持群聊和私聊场景
- 可配置监控白名单/黑名单
- 可独立开关各分析维度
- 冷却机制防止 LLM 过度调用
- 支持回复模式和私聊模式

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

        # -------- 基础配置 --------
        self.enabled: bool = config.get("enabled", True)
        self.provider_id: str = config.get("provider_id", "")
        self.analysis_mode: str = config.get("analysis_mode", "standard")

        # -------- 监控配置 --------
        self.monitor_mode: str = config.get("monitor_mode", "whitelist")
        self.monitored_groups: set = set(config.get("monitored_groups", []))
        self.monitored_users: set = set(config.get("monitored_users", []))
        self.excluded_users: set = set(config.get("excluded_users", []))

        # -------- 分析配置 --------
        self.enable_intent: bool = config.get("enable_intent_analysis", True)
        self.enable_emotion: bool = config.get("enable_emotion_detection", True)
        self.enable_danger: bool = config.get("enable_danger_assessment", True)
        self.enable_action: bool = config.get("enable_action_advice", True)
        self.danger_threshold: int = config.get("danger_threshold", 7)
        self.context_count: int = max(1, min(50, config.get("context_message_count", 10)))

        # -------- 回复配置 --------
        self.response_mode: str = config.get("response_mode", "reply")
        self.cooldown_seconds: int = max(5, config.get("cooldown_seconds", 30))

        # -------- 高级配置 --------
        self.custom_prompt: str = config.get("custom_system_prompt", "")

        # -------- 内部状态 --------
        self._buffers: dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        self._last_analysis: dict[str, float] = defaultdict(float)
        self._analysis_count: int = 0
        self._error_count: int = 0

        logger.info(
            f"[ChatHelper] v{VERSION} 加载完成 | "
            f"启用={self.enabled} 监控={self.monitor_mode} "
            f"分析={self.analysis_mode} 冷却={self.cooldown_seconds}s"
        )

    # ================================================================
    #  消息监听
    # ================================================================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """
        监听全部消息，按配置过滤后调用 LLM 进行对话分析。
        """
        try:
            if not self.enabled:
                return

            sender_id = event.get_sender_id()
            sender_name = event.get_sender_name()
            message_str = event.message_str.strip()
            group_id = event.message_obj.group_id or ""
            session_id = event.session_id

            # 跳过空消息
            if not message_str:
                return

            # 跳过机器人自身消息
            if self._is_self_message(event, sender_id):
                return

            # 监控范围过滤
            if not self._should_monitor(sender_id, group_id, session_id):
                return

            # 冷却检查
            now = time.time()
            if now - self._last_analysis[session_id] < self.cooldown_seconds:
                return

            # 存入消息缓冲
            self._buffers[session_id].append(
                {
                    "sender_id": sender_id,
                    "sender_name": sender_name,
                    "content": message_str,
                    "timestamp": datetime.now().strftime("%H:%M"),
                    "is_self": False,
                }
            )

            # 执行 LLM 分析
            analysis = await self._call_llm(event, session_id, sender_name, message_str)

            if analysis:
                response = self._format_response(sender_name, message_str, analysis)

                # 根据回复模式发送
                if self.response_mode == "private":
                    success = await self._try_send_private(event, sender_id, response)
                    if not success:
                        # 私聊失败则回退到会话内回复
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

    def _should_monitor(self, sender_id: str, group_id: str, session_id: str) -> bool:
        """根据监控模式判断是否需要处理此消息"""
        # 排除列表优先级最高
        if sender_id in self.excluded_users:
            return False

        if self.monitor_mode == "all":
            return True

        if self.monitor_mode == "whitelist":
            return self._match_whitelist(sender_id, group_id, session_id)

        if self.monitor_mode == "blacklist":
            return self._match_blacklist(sender_id, group_id, session_id)

        return False

    def _match_whitelist(self, sender_id: str, group_id: str, session_id: str) -> bool:
        """白名单匹配逻辑：名单中任一条件命中即通过"""
        # 两个名单都为空 → 不监控
        if not self.monitored_groups and not self.monitored_users:
            return False

        # 群组命中
        if self.monitored_groups:
            if group_id in self.monitored_groups or session_id in self.monitored_groups:
                return True

        # 用户命中
        if self.monitored_users:
            if sender_id in self.monitored_users:
                return True

        return False

    def _match_blacklist(self, sender_id: str, group_id: str, session_id: str) -> bool:
        """黑名单匹配逻辑：命中任一条件即排除"""
        if self.monitored_groups:
            if group_id in self.monitored_groups or session_id in self.monitored_groups:
                return False

        if self.monitored_users:
            if sender_id in self.monitored_users:
                return False

        return True

    # ================================================================
    #  LLM 分析
    # ================================================================

    async def _call_llm(
        self,
        event: AstrMessageEvent,
        session_id: str,
        sender_name: str,
        current_message: str,
    ) -> Optional[str]:
        """调用 LLM 进行对话分析，返回分析文本或 None"""
        try:
            # 获取上下文快照
            context_snapshot = list(self._buffers[session_id])[-self.context_count :]

            # 构建完整提示词
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(
                context_snapshot, sender_name, current_message
            )
            full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"

            # 确定 LLM 提供商
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

            # 调用 LLM
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

        # 至少保留意图分析
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
    ) -> str:
        """组装用户提示词（上下文 + 当前消息 + 分析指令）"""
        # 格式化上下文
        if context:
            lines = []
            for msg in context:
                tag = "我" if msg.get("is_self") else msg["sender_name"]
                lines.append(f"[{msg['timestamp']}] {tag}: {msg['content']}")
            context_text = "\n".join(lines)
        else:
            context_text = "（暂无历史记录）"

        mode_hint = MODE_INSTRUCTIONS.get(
            self.analysis_mode, MODE_INSTRUCTIONS["standard"]
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
        txt = (
            f"📋 聊天助手状态 (v{VERSION})\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"启用: {'✅' if self.enabled else '❌'}\n"
            f"监控模式: {self.monitor_mode}\n"
            f"分析模式: {self.analysis_mode}\n"
            f"冷却时间: {self.cooldown_seconds}s\n"
            f"回复模式: {self.response_mode}\n\n"
            f"📊 统计\n"
            f"已分析: {self._analysis_count} 次\n"
            f"错误: {self._error_count} 次\n\n"
            f"📂 名单\n"
            f"群组: {len(self.monitored_groups)} | "
            f"用户: {len(self.monitored_users)} | "
            f"排除: {len(self.excluded_users)}\n\n"
            f"🔍 分析维度\n"
            f"意图 {'✅' if self.enable_intent else '❌'} | "
            f"情绪 {'✅' if self.enable_emotion else '❌'} | "
            f"风险 {'✅' if self.enable_danger else '❌'} | "
            f"建议 {'✅' if self.enable_action else '❌'}"
        )
        yield event.plain_result(txt)

    @chat_helper_cmd.command("on")
    async def cmd_on(self, event: AstrMessageEvent):
        """启用插件"""
        self.enabled = True
        yield event.plain_result("✅ 聊天助手已启用")

    @chat_helper_cmd.command("off")
    async def cmd_off(self, event: AstrMessageEvent):
        """禁用插件"""
        self.enabled = False
        yield event.plain_result("❌ 聊天助手已禁用")

    @chat_helper_cmd.command("mode")
    async def cmd_mode(self, event: AstrMessageEvent, mode: str = ""):
        """切换分析模式: quick / standard / detailed"""
        if mode in MODE_INSTRUCTIONS:
            self.analysis_mode = mode
            yield event.plain_result(f"✅ 分析模式已切换为: {mode}")
        else:
            available = " / ".join(MODE_INSTRUCTIONS.keys())
            yield event.plain_result(
                f"用法: /chat_helper mode <模式>\n"
                f"可用: {available}\n"
                f"当前: {self.analysis_mode}"
            )

    # ================================================================
    #  生命周期
    # ================================================================

    async def terminate(self):
        """插件卸载时清理资源"""
        self._buffers.clear()
        self._last_analysis.clear()
        logger.info("[ChatHelper] 插件已卸载")
