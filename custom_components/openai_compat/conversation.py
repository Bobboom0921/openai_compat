"""对话平台:定义 ConversationEntity,用 aiohttp 直连 OpenAI 兼容 /chat/completions。"""
import logging

import aiohttp

from homeassistant.components.conversation import (
    AssistantContent,
    ChatLog,
    ConversationEntity,
    ConversationEntityFeature,
    ConversationInput,
    ConversationResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_BASE_URL, CONF_MODEL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([OpenAICompatEntity(hass, entry)])


class OpenAICompatEntity(ConversationEntity):
    """一个能以任意 OpenAI 兼容端点对话的 conversation 实体。"""

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
        session = self._cfg["session"]
        base = (cfg.get(CONF_BASE_URL) or "").rstrip("/")
        model = cfg.get(CONF_MODEL) or "deepseek-v3"
        api_key = cfg.get(CONF_API_KEY, "")

        url = f"{base}/chat/completions"

        # 由 HA 自动维护的聊天历史 -> OpenAI messages(带系统提示)
        messages = [
            {
                "role": "system",
                "content": (
                    "你是智能家居的对话引擎,用简体中文简洁回答。"
                    "可根据上下文里的家庭状态信息辅助回答。"
                ),
            }
        ]
        for item in chat_log.content:
            content = getattr(item, "content", None)
            if not content:
                continue
            messages.append({"role": item.role, "content": content})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 1024,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with session.post(
                url,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60),
            ) as resp:
                body = await resp.json(content_type=None)
                if resp.status != 200:
                    _LOGGER.error(
                        "OpenAI compat %s 返回 %s: %s", model, resp.status, body
                    )
                    content = f"上游返回错误 {resp.status}"
                else:
                    content = (
                        (body.get("choices") or [{}])[0]
                        .get("message", {})
                        .get("content")
                        or "(空回复)"
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("OpenAI compat 请求失败: %s", err)
            content = f"请求失败: {err}"

        chat_log.async_add_assistant_content_without_tools(
            AssistantContent(
                agent_id=user_input.agent_id,
                content=content,
            )
        )
        response = intent.IntentResponse(language=user_input.language)
        response.async_set_speech(content)
        return ConversationResult(
            conversation_id=user_input.conversation_id,
            response=response,
            continue_conversation=False,
        )