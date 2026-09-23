"""
内置消息模板模块。

提供统一的现代化纯文本卡片样式，用于状态、统计、帮助和分析结果展示。
所有模板使用 Unicode 框线字符模拟卡片效果，兼容各平台纯文本渲染。
"""

from __future__ import annotations

import json
import re
from typing import Any

# ==================== 样式常量 ====================

WIDTH = 50
TOP_LEFT = "┌"
TOP_RIGHT = "┐"
BOTTOM_LEFT = "└"
BOTTOM_RIGHT = "┘"
HORIZONTAL = "─"
VERTICAL = "│"
DIVIDER_LEFT = "├"
DIVIDER_RIGHT = "┤"
PROGRESS_FULL = "█"
PROGRESS_EMPTY = "░"


# ==================== 渲染辅助 ====================


def _pad_center(text: str, width: int = WIDTH) -> str:
    """将文本居中填充到指定宽度。"""
    if len(text) >= width:
        return text
    total_pad = width - len(text)
    left_pad = total_pad // 2
    right_pad = total_pad - left_pad
    return " " * left_pad + text + " " * right_pad


def _pad_right(text: str, width: int = WIDTH) -> str:
    """将文本右填充到指定宽度。"""
    if len(text) >= width:
        return text
    return text + " " * (width - len(text))


def render_card(title: str, body: str, width: int = WIDTH) -> str:
    """
    渲染统一卡片样式。

    示例：
    ┌────────────────────────────────────────┐
    │           💬 对话分析报告               │
    ├────────────────────────────────────────┤
    │ 对象: 小明                               │
    │ ...                                    │
    └────────────────────────────────────────┘
    """
    lines = []
    top = f"{TOP_LEFT}{HORIZONTAL * width}{TOP_RIGHT}"
    divider = f"{DIVIDER_LEFT}{HORIZONTAL * width}{DIVIDER_RIGHT}"
    bottom = f"{BOTTOM_LEFT}{HORIZONTAL * width}{BOTTOM_RIGHT}"

    lines.append(top)
    lines.append(f"{VERTICAL}{_pad_center(title, width)}{VERTICAL}")
    lines.append(divider)

    for line in body.split("\n"):
        # 对超长行做简单截断，保持卡片边界
        if len(line) > width:
            line = line[: width - 3] + "..."
        lines.append(f"{VERTICAL}{_pad_right(line, width)}{VERTICAL}")

    lines.append(bottom)
    return "\n".join(lines)


def render_progress_bar(
    value: float, max_value: float = 10, width: int = 20
) -> str:
    """渲染进度条，如 ████████░░░░░░░░░░░░ 4/10。"""
    if max_value <= 0:
        max_value = 1
    filled = int(round(width * min(value, max_value) / max_value))
    bar = PROGRESS_FULL * filled + PROGRESS_EMPTY * (width - filled)
    return f"{bar} {value:g}/{max_value:g}"


# ==================== 模板定义 ====================

STATUS_TEMPLATE = """启用状态: {enabled}
群监控: {group_mode} ({group_count})
用户监控: {user_mode} ({user_count})
分析模式: {analysis_mode} (本群)
冷却时间: {cooldown}s
回复模式: {response_mode}"""

STATS_TEMPLATE = """已分析: {analysis_count} 次
错误: {error_count} 次

[配置概览]
群名单: {group_count}
用户名单: {user_count}
被分析用户: {analysis_user_count}
群模式配置: {mode_group_count}

[分析维度]
意图: {intent_status}
情绪: {emotion_status}
风险: {danger_status}
建议: {action_status}
当前群模式: {current_mode}"""

HELP_TEMPLATE = """用法: /chat_helper <命令> [参数]

命令列表:
  status          查看插件运行状态
  stats           查看分析统计和配置概览
  mode <模式>      切换本群分析模式
  analyze <ID> <add|remove>  设置被分析用户

模式: quick / standard / detailed"""

ANALYSIS_FALLBACK_TEMPLATE = """对象: {sender_name}
消息: 「{message}」

{analysis_text}"""


# ==================== 分析结果渲染 ====================


def render_analysis(
    sender_name: str,
    message: str,
    analysis: str,
    enable_intent: bool = True,
    enable_emotion: bool = True,
    enable_danger: bool = True,
    enable_action: bool = True,
) -> str:
    """
    渲染对话分析结果为统一卡片。

    优先尝试解析 LLM 返回的 JSON 结构化数据；
    解析失败则回退到纯文本包装。
    """
    display_msg = message[:40] + ("..." if len(message) > 40 else "")

    # 尝试提取 JSON
    data = _extract_json(analysis)
    if data is None:
        # 回退：纯文本包装
        body = ANALYSIS_FALLBACK_TEMPLATE.format(
            sender_name=sender_name,
            message=display_msg,
            analysis_text=analysis.strip(),
        )
        return render_card("💬 对话分析报告", body)

    # 结构化渲染
    lines = [f"对象: {sender_name}", f"消息: 「{display_msg}」", ""]

    if enable_intent and "intent" in data:
        intent = data["intent"]
        lines.append("📊 意图解读")
        if isinstance(intent, dict):
            surface = intent.get("surface", "")
            if surface:
                lines.append(f"表面: {surface}")
            real = intent.get("real", "")
            if real:
                lines.append(f"真实: {real}")
            other = intent.get("other", "")
            if other:
                lines.append(f"其他: {other}")
        else:
            lines.append(str(intent))
        lines.append("")

    if enable_emotion and "emotion" in data:
        emotion = data["emotion"]
        lines.append("❤️ 情绪评估")
        if isinstance(emotion, dict):
            lines.append(f"状态: {emotion.get('state', '未知')}")
            intensity = emotion.get("intensity", 0)
            if intensity:
                lines.append(
                    f"强度: {render_progress_bar(intensity, 10, 16)}"
                )
            trend = emotion.get("trend", "")
            if trend:
                lines.append(f"趋势: {trend}")
        else:
            lines.append(str(emotion))
        lines.append("")

    if enable_danger and "danger" in data:
        danger = data["danger"]
        lines.append("⚠️ 风险等级")
        if isinstance(danger, dict):
            level = danger.get("level", 0)
            lines.append(render_progress_bar(level, 10, 20))
            dtype = danger.get("type", "")
            if dtype:
                lines.append(f"类型: {dtype}")
            note = danger.get("note", "")
            if note:
                lines.append(f"说明: {note}")
        else:
            lines.append(str(danger))
        lines.append("")

    if enable_action and "action" in data:
        action = data["action"]
        lines.append("💡 回应建议")
        if isinstance(action, list):
            for idx, item in enumerate(action, 1):
                if isinstance(item, dict):
                    strategy = item.get("strategy", "")
                    prob = item.get("probability", "")
                    if prob:
                        lines.append(f"{idx}. {strategy} ({prob})")
                    else:
                        lines.append(f"{idx}. {strategy}")
                else:
                    lines.append(f"{idx}. {item}")
        else:
            lines.append(str(action))

    body = "\n".join(lines).rstrip()
    return render_card("💬 对话分析报告", body)


def _extract_json(text: str) -> dict[str, Any] | None:
    """
    从 LLM 输出中提取 JSON 对象。

    支持两种格式：
    1. 纯 JSON 对象
    2. 被 ```json ... ``` 包裹的代码块
    """
    text = text.strip()

    # 尝试直接解析
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass

    # 尝试提取 ```json 代码块
    match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(1).strip())
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    return None
