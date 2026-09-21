"""
AstrBot API 桩模块。

在没有安装完整 AstrBot 运行时的环境中，
通过注入 sys.modules 使 main.py 可以被导入和测试。
"""

from __future__ import annotations

import sys
import types
from unittest.mock import Mock


def _noop_decorator(*args, **kwargs):
    """替代 AstrBot 的 filter 装饰器，原样返回被装饰的函数。"""
    del args, kwargs
    return lambda function: function


def install_astrbot_stubs() -> Mock:
    """注入 AstrBot API 桩模块，返回可用于断言的 logger Mock。"""
    logger = Mock()

    # astrbot.api
    astrbot = types.ModuleType("astrbot")
    astrbot.__path__ = []
    api = types.ModuleType("astrbot.api")
    api.__path__ = []
    api.AstrBotConfig = dict
    api.logger = logger

    # astrbot.api.event
    event = types.ModuleType("astrbot.api.event")
    event.AstrMessageEvent = type("AstrMessageEvent", (), {})
    event.MessageChain = type("MessageChain", (), {})
    event.filter = types.SimpleNamespace(
        command=_noop_decorator,
        command_group=lambda *a, **kw: _noop_decorator,
        event_message_type=_noop_decorator,
        permission_type=_noop_decorator,
        EventMessageType=types.SimpleNamespace(
            ALL=object(),
            GROUP_MESSAGE=object(),
            PRIVATE_MESSAGE=object(),
        ),
    )

    # astrbot.api.star
    star = types.ModuleType("astrbot.api.star")
    star.Context = type("Context", (), {})
    star.Star = type("Star", (), {})

    sys.modules.update({
        "astrbot": astrbot,
        "astrbot.api": api,
        "astrbot.api.event": event,
        "astrbot.api.star": star,
    })
    return logger


LOGGER = install_astrbot_stubs()
