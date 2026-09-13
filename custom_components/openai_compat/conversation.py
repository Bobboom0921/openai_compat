"""对话平台:定义 ConversationEntity,走 HA 标准 conversation + llm 协议。

2.0.0 起改为「协议合规」大脑:
- 调用 ChatLog.async_provide_llm_data() 触发 HA/Claw 注入工具(chat_log.llm_api.tools)
- 用 aiohttp 直连任意 OpenAI 兼容 /chat/completions 端点(火山方舟/硅基流动等)
- 解析返回的 tool_calls,交给 chat_log.async_add_assistant_content() 执行工具
- 工具结果回喂模型,循环直到不再有工具调用

这样能让 Claw Assistant 等依赖 HA llm 协议的多轮工具循环真正驱动设备,
而不是只回一句"已打开"却不动作。
"""
from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp
from voluptuous_openapi import convert  # HA 稳定版自带,2026.8 官方 openai 同款

from homeassistant.components import conversation
from homeassistant.components.conversation import (
    AssistantContent,
    ChatLog,
    ConversationEntity,
    ConversationEntityFeature,
    ConversationInput,
    ConversationResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_PROMPT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_BASE_URL, CONF_LLM_HASS_API, CONF_MAX_TOKENS, CONF_MODEL, CONF_TEMPERATURE, DOMAIN

_LOGGER = logging.getLogger(__name__)

# 与 LLM 的最大往返次数,防止工具死循环
MAX_TOOL_ITERATIONS = 10


def _format_tool(tool: llm.Tool) -> dict[str, Any]:
    """把一个 HA llm.Tool 转成 OpenAI 兼容的 function tool schema。

    与官方 openai_conversation(2026.8.3) 的 _format_tool 同构:
    用 voluptuous_openapi.convert 序列化,并剔除 vol 生成的不被 OpenAI 接受的键。
    """
    unsupported_keys = {"oneOf", "anyOf", "allOf", "enum", "not"}
    schema = convert(tool.parameters, custom_serializer=llm.selector_serializer)
    if unsupported_keys.intersection(schema):
        schema = {k: v for k, v in schema.items() if k not in unsupported_keys}
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": schema,
        },
    }


def _content_to_openai_messages(
    chat_content: list[conversation.Content],
) -> list[dict[str, Any]]:
    """把 HA 原生 chat_log.content 转成 OpenAI messages。"""
    messages: list[dict[str, Any]] = []
    for content in chat_content:
        if isinstance(content, conversation.SystemContent):
            messages.append({"role": "system", "content": content.content})
            continue

        if isinstance(content, conversation.UserContent):
            messages.append({"role": "user", "content": content.content})
            continue

        if isinstance(content, conversation.AssistantContent):
            msg: dict[str, Any] = {"role": "assistant"}
            if content.content:
                msg["content"] = content.content
            if content.tool_calls:
                msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.tool_name,
                            "arguments": json.dumps(tc.tool_args, ensure_ascii=False),
                        },
                    }
                    for tc in content.tool_calls
                ]
            messages.append(msg)
            continue

        if isinstance(content, conversation.ToolResultContent):
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": content.tool_call_id,
                    "content": json.dumps(content.tool_result, ensure_ascii=False),
                }
            )
            continue

    return messages


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([OpenAICompatEntity(hass, entry)])


class OpenAICompatEntity(ConversationEntity):
    """一个能以任意 OpenAI 兼容端点对话、并走 HA llm 工具协议的大脑。"""

    _attr_has_entity_name = True
    capable_language = "zh-CN"
    supported_languages = [
        "zh-CN", "en", "ja", "ko", "de", "es", "fr", "it",
        "pt", "ru", "tr", "uk", "pl", "nl",
    ]

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """初始化:绑定配置条目与实体 ID。"""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.title

    @property
    def _cfg(self):
        return self.hass.data[DOMAIN][self._entry.entry_id]

    @property
    def supported_features(self):
        return ConversationEntityFeature.CONTROL

    async def _async_handle_message(
        self, user_input: ConversationInput, chat_log: ChatLog
    ) -> ConversationResult:
        cfg = self._cfg["data"]

        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                user_llm_hass_api=cfg.get(CONF_LLM_HASS_API) or "assist",
                user_llm_prompt=cfg.get(CONF_PROMPT),
                user_extra_system_prompt=user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        await self._async_handle_chat_log(chat_log)

        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    async def _async_handle_chat_log(self, chat_log: ChatLog) -> None:
        """生成回答:循环调用 /chat/completions,执行工具直到收敛。"""
        cfg = self._cfg["data"]
        session = self._cfg["session"]
        base = (cfg.get(CONF_BASE_URL) or "").rstrip("/")
        model = cfg.get(CONF_MODEL) or "deepseek-v3"
        api_key = cfg.get(CONF_API_KEY, "")

        url = f"{base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        llm_api = chat_log.llm_api
        if llm_api is None:
            _LOGGER.error("No LLM API configured; 无法调用工具")
            content = AssistantContent(
                agent_id=self.entity_id,
                content="(未配置 LLM API,无法继续)",
            )
            chat_log.async_add_assistant_content_without_tools(content)
            return

        tools = [_format_tool(tool) for tool in llm_api.tools]

        # 维护一个随多轮累积的 OpenAI messages
        api_messages = _content_to_openai_messages(chat_log.content)

        for _iteration in range(MAX_TOOL_ITERATIONS):
            payload: dict[str, Any] = {
                "model": model,
                "messages": api_messages,
                "temperature": cfg.get(CONF_TEMPERATURE, 0.2),
                "max_tokens": cfg.get(CONF_MAX_TOKENS, 1024),
            }
            if tools:
                payload["tools"] = tools

            try:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    body = await resp.json(content_type=None)
                    if resp.status != 200:
                        _LOGGER.error(
                            "OpenAI compat %s 返回 %s: %s", model, resp.status, body
                        )
                        content = AssistantContent(
                            agent_id=self.entity_id,
                            content=f"上游返回错误 {resp.status}",
                        )
                        chat_log.async_add_assistant_content_without_tools(content)
                        return
                    message = (body.get("choices") or [{}])[0].get("message", {})
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("OpenAI compat 请求失败: %s", err)
                content = AssistantContent(
                    agent_id=self.entity_id,
                    content=f"请求失败: {err}",
                )
                chat_log.async_add_assistant_content_without_tools(content)
                return

            # 记录这次回包,便于后续轮次把它作为 assistant 消息回喂
            api_messages.append(
                {
                    "role": "assistant",
                    "content": message.get("content") or None,
                }
            )

            tool_calls = message.get("tool_calls")
            if not tool_calls:
                # 模型给出了最终文本回答,写入历史后结束
                content = AssistantContent(
                    agent_id=self.entity_id,
                    content=message.get("content") or "(空回复)",
                )
                chat_log.async_add_assistant_content_without_tools(content)
                if message.get("content") is None:
                    _LOGGER.warning("模型未返回内容且未调用工具,可能已无可用工具")
                return

            # 模型决定调用工具:构建 assistant content + tool_calls,交给 HA 执行
            assistant_tool_inputs = [
                llm.ToolInput(
                    id=tc["id"],
                    tool_name=tc.get("function", {}).get("name", ""),
                    tool_args=json.loads(tc.get("function", {}).get("arguments") or "{}"),
                )
                for tc in tool_calls
            ]

            # 同步 assistant_messages 里的 tool_calls,否则下一轮 OpenAI 会报缺工具调用
            api_messages[-1]["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": tc.get("function", {}).get("arguments", "{}"),
                    },
                }
                for tc in tool_calls
            ]

            # 注意:这里的 tool_calls 必须是非 external 的,交由 HA 执行
            content = AssistantContent(
                agent_id=self.entity_id,
                content=message.get("content"),
                tool_calls=assistant_tool_inputs,
            )

            collected_results: dict[str, Any] = {}
            async for result in chat_log.async_add_assistant_content(content):
                collected_results[result.tool_call_id] = result

            # 把工具结果作为 tool 消息追加回 OpenAI messages
            for tc in tool_calls:
                tool_result = collected_results.get(tc["id"])
                content_json = (
                    json.dumps(tool_result.tool_result, ensure_ascii=False)
                    if tool_result is not None
                    else "{}"
                )
                api_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": content_json,
                    }
                )

        # 超限:给个提示避免静默失败
        content = AssistantContent(
            agent_id=self.entity_id,
            content="(已达到工具调用次数上限)",
        )
        chat_log.async_add_assistant_content_without_tools(content)