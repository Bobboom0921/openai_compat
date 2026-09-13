"""配置向导:收集 Base URL / API Key / Model,并支持配置后重新修改。"""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_BASE_URL,
    CONF_LLM_HASS_API,
    CONF_MAX_TOKENS,
    CONF_MODEL,
    CONF_TEMPERATURE,
    DOMAIN,
)

_DEFAULT_BASE = "https://ark.cn-beijing.volces.com/api/v3"


def _schema(defaults: dict) -> vol.Schema:
    """按现有配置(或首次默认值)构造向导表单。"""
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME, "火山方舟")
            ): str,
            vol.Required(
                CONF_BASE_URL, default=defaults.get(CONF_BASE_URL, _DEFAULT_BASE)
            ): str,
            vol.Required(
                CONF_API_KEY, default=defaults.get(CONF_API_KEY, "")
            ): str,
            vol.Required(
                CONF_MODEL, default=defaults.get(CONF_MODEL, "deepseek-v3")
            ): str,
            vol.Optional(
                CONF_TEMPERATURE,
                default=defaults.get(CONF_TEMPERATURE, 0.2),
                description={"suggested_value": defaults.get(CONF_TEMPERATURE, 0.2)},
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX,
                    min=0,
                    max=2,
                    step=0.1,
                )
            ),
            vol.Optional(
                CONF_MAX_TOKENS,
                default=defaults.get(CONF_MAX_TOKENS, 1024),
                description={"suggested_value": defaults.get(CONF_MAX_TOKENS, 1024)},
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    mode=selector.NumberSelectorMode.BOX,
                    min=256,
                    max=8192,
                    step=256,
                )
            ),
            # HA assist 工具开关:开启则让模型具备控制 HA 设备的能力(兼容 Claw)
            vol.Optional(
                "enable_assist",
                default=defaults.get(CONF_LLM_HASS_API, "assist") is not None,
                description={
                    "suggested_value": defaults.get(CONF_LLM_HASS_API, "assist")
                    is not None
                },
            ): selector.BooleanSelector(),
        }
    )


def _finalize_data(user_input: dict) -> dict:
    """把表单数据转成实际存储的配置(assist 开关 -> llm_hass_api)。"""
    data = dict(user_input)
    enable_assist = bool(data.pop("enable_assist", True))
    data[CONF_LLM_HASS_API] = "assist" if enable_assist else None
    return data


class OpenAIModConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    MINOR_VERSION = 1

    @staticmethod
    def async_get_options_flow(entry):
        return OpenAIModOptionsFlow(entry)

    async def async_step_user(self, user_input=None):
        """首次添加集成。"""
        errors = {}
        if user_input is not None:
            if not user_input.get(CONF_API_KEY):
                errors[CONF_API_KEY] = "need_api_key"
            else:
                data = _finalize_data(user_input)
                if not data.get(CONF_LLM_HASS_API):
                    del data[CONF_LLM_HASS_API]
                return self.async_create_entry(
                    title=data[CONF_NAME], data=data
                )
        return self.async_show_form(
            step_id="user", data_schema=_schema({}), errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        """在设备与服务里点「配置」时修改已有条目的参数。"""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            if not user_input.get(CONF_API_KEY):
                errors[CONF_API_KEY] = "need_api_key"
            else:
                data = _finalize_data(user_input)
                if not data.get(CONF_LLM_HASS_API):
                    del data[CONF_LLM_HASS_API]
                return self.async_update_reentry_and_finish(
                    data=data,
                    title=data[CONF_NAME],
                )
        return self.async_show_form(
            step_id="reconfigure", data_schema=_schema(dict(entry.data)), errors=errors
        )


class OpenAIModOptionsFlow(config_entries.OptionsFlow):
    """选项流程:允许独立于基础信息调整(最小实现,便于将来扩展)。"""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init", data_schema=vol.Schema({})
        )