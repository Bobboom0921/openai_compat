"""配置向导:收集 Base URL / API Key / Model,并支持配置后重新修改。"""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME

from .const import CONF_BASE_URL, CONF_MODEL, DOMAIN

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
        }
    )


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
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
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
                return self.async_update_reentry_and_finish(
                    data=user_input,
                    title=user_input[CONF_NAME],
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