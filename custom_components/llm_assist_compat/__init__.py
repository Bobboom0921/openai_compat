"""HA 2026.8 兼容层:为旧协议组件(如 Claw Assistant)补回被官方重构删掉的 AssistAPI。

背景:
- HA ≤ 2026.7 在 homeassistant.helpers.llm 里定义 `class AssistAPI`,
  Claw Assistant 等组件依赖其 `_async_get_api_prompt` / `_async_get_tools` / `async_get_api_instance` 打 patch。
- HA 2026.8 重构了 LLM 协议(改为 async_register_api + async_get_apis 注册制),
  从 helpers.llm 删除了 AssistAPI,导致仍按旧接口挂载的组件 `AttributeError` 启动失败。

本集成只做一件事:在 Claw 加载前,把 AssistAPI 以静态桩形式补回 llm 模块,
让旧组件的 snapshot/patch 不再崩。2026.8 的 assist 走的是新协议,不真正调用这个类,
因此桩方法只需「存在且可调用」,无需复制官方旧实现。
"""
from __future__ import annotations

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def _inject_assist_api() -> bool:
    """幂等地给 homeassistant.helpers.llm 注入 AssistAPI 桩,返回是否执行了注入。"""
    import homeassistant.helpers.llm as llm

    if hasattr(llm, "AssistAPI"):
        # 旧版 HA 本就自带,无需注入
        return False

    class AssistAPI:
        """AssistAPI 兼容桩(HA 2026.8 删除后由本扩展补回)。

        供 Claw Assistant 等旧协议组件在启动时抓快照 / 打 patch 使用。
        """

        IGNORE_INTENTS = frozenset()

        def __init__(self, hass: Any = None) -> None:
            self.hass = hass
            self.cached_slugify = None

        @staticmethod
        def _async_get_api_prompt(_llm_context, _exposed_entities=None) -> str:
            """(@callback)辅助 API 提示词。桩:2026.8 不通过本类取 assist 提示。"""
            return ""

        @staticmethod
        def _async_get_tools(_llm_context, _exposed_entities=None):
            """(@callback)开发辅助工具列表。桩:2026.8 不通过本类取 assist 工具。"""
            return []

        @staticmethod
        async def async_get_api_instance(_llm_context):
            """返回 API 实例。桩:返回值不会被新协议消费。"""
            return None

    llm.AssistAPI = AssistAPI  # type: ignore[attr-defined]
    _LOGGER.info("已向 homeassistant.helpers.llm 注入 AssistAPI 兼容桩(HA 2026.8)")
    return True


async def async_setup(hass, _config=None) -> bool:
    """HA 加载本集成时注入兼容类。"""
    _inject_assist_api()
    return True