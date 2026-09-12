"""OpenAI Compatible Conversation component.

轻量对话集成:用 aiohttp 直连任意 OpenAI 兼容端点(火山方舟/硅基流动/OpenRouter 等),
不依赖 python-openai 库,故不会与 HA 自身依赖的 openai 版本冲突。
"""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import CONF_BASE_URL, CONF_MODEL, DOMAIN

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.CONVERSATION]

_DEFAULT_BASE = "https://ark.cn-beijing.volces.com/api/v3"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """设置配置条目:建立会话、存数据,转发到 conversation 平台。"""
    data = dict(entry.data)
    data.setdefault(CONF_BASE_URL, _DEFAULT_BASE)
    data.setdefault(CONF_MODEL, "deepseek-v3")
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "data": data,
        "session": aiohttp_client.async_get_clientsession(hass),
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_update_listener))
    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """配置变化(local options)时刷新保存的数据与会话。"""
    data = dict(entry.data)
    data.setdefault(CONF_BASE_URL, _DEFAULT_BASE)
    data.setdefault(CONF_MODEL, "deepseek-v3")
    hass.data[DOMAIN][entry.entry_id]["data"] = data
    hass.data[DOMAIN][entry.entry_id]["session"] = aiohttp_client.async_get_clientsession(hass)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return ok