# OpenAI Compatible Conversation

[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/Bobboom0921/openai_compat)
[![GitHub Release](https://img.shields.io/github/v/release/Bobboom0921/openai_compat)](https://github.com/Bobboom0921/openai_compat/releases)
[![HA](https://img.shields.io/static/v1.svg?label=HA&message=2026.8%2B&color=3498db)](https://github.com/Bobboom0921/openai_compat)

一个**轻量、通用**的 Home Assistant 对话集成。用 aiohttp 直连任意 **OpenAI 兼容** `POST /chat/completions` 端点，让外部大模型服务成为 HA 的对话智能体（Assistant / Assist Pipeline / Claw Assistant 可用）。

> 不依赖 `python-openai` 库 → 不与你 HA 自带的 `openai` 版本冲突，`RequirementsNotFound` 死锁从此消失。

---

## 特性

- 零 Python 依赖，只用一个内置的 aiohttp 请求，装完即可用。
- **任意 OpenAI 兼容服务商**：火山方舟、硅基流动、OpenRouter、DeepSeek 官方、本地 Ollama / vLLM 网关等，只改 Base URL 即可切换。
- **真正的多轮对话**：自动利用 HA 的 `chat_log` 历史，把前几轮上下文喂进 messages，不再只发当句话。
- **工具调用（function calling）**：接入 HA 标准 `llm` 工具协议，兼容 Claw Assistant 等多轮工具循环，可真正执行设备控制（开/关灯、调空调、场景等），而非只回复不动作。
- 配置后可随时「配置」改 Base URL / API Key / Model，无需删了重建。
- 内置简体中文配置向导与错误提示。
- 兼容 HA Core **2026.8**（`ConversationEntity` 新协议）。

---

## 安装

### 方式一：HACS（推荐）

1. HACS → 右上角 **三个点** → **自定义存储库**。
2. 存储库填 `https://github.com/Bobboom0921/openai_compat`，类别选 **集成 (Integration)**，添加。
3. HACS → **集成** → 搜索 **OpenAI Compatible Conversation** → 安装。
4. 重启 Home Assistant。
5. **设置 → 设备与服务 → 添加集成** → 搜索 `OpenAI Compatible Conversation`。

> 更新：HACS 会在有新 Release 时提示一键升级（版本号来自 GitHub Release 的 `v*` tag）。

### 方式二：手动

1. 把 `custom_components/openai_compat` 整个文件夹放到：
   ```
   <配置目录>/custom_components/openai_compat/
   ```
2. 重启 Home Assistant。
3. **设置 → 设备与服务 → 添加集成** → 搜索 `OpenAI Compatible Conversation`。

---

## 配置

| 字段       | 说明                                                                   |
|------------|-----------------------------------------------------------------------|
| Name       | 集成显示名，例如「火山方舟」                                             |
| Base URL   | OpenAI 兼容的 API 根地址，默认火山方舟 `…/api/v3`，末尾**不带** `/chat/completions` |
| API Key    | 你的服务商 API Key                                                     |
| Model      | 模型 / 接入点 ID（火山方舟用 `ep-…` 或模型名，详见下方排查）               |
| 温度       | 抽样随机性 0–2，默认 0.2                                                 |
| 最大输出 Token | 单次回答长度上限，默认 1024                                            |
| 启用 HA 设备控制工具 | 开启后接入 HA 工具协议（assist / Claw 多轮工具循环），可真正调用 `light.turn_on` 等控制设备 |

添加后会出现一个 `conversation.*` 对话实体（名字 = 你填的 Name）。在 **开发者工具 → 对话** 选它即可测试。

> 之后想改参数：**设备与服务 → 该集成 → 配置**。

---

## 火山方舟 404 排查

方舟 `POST /api/v3/chat/completions` 返回 **404** 几乎都是 **Model 名在你的账号下不存在**（Key 错会返回 401，不是 404）。

查看你账号真实可用的模型/接入点 ID：

```bash
curl -H "Authorization: Bearer 你的KEY" \
  https://ark.cn-beijing.volces.com/api/v3/models
```

- 返回 `data[].id` 形如 `ep-2026xxxx-xxxxx`（接入点 ID）或 `deepseek-v3-250630`（模型 ID）。
- 把该 ID 填进配置的 **Model** 即可。
- 接入点要先去火山方舟控制台「在线推理 → 接入点」创建。

---

## 换一家服务商

只需在配置里把 **Base URL** 与 **Model** 换成目标服务的值，例如：

- 硅基流动：`https://api.siliconflow.cn/v1` + 模型 ID
- OpenRouter：`https://openrouter.ai/api/v1` + `org/model`
- Ollama：`http://<host>:11434/v1` + 本地模型名

---

## 兼容性

- 基于 HA Core **2026.8** 的 `ConversationEntity` 新协议编写。
- 零额外依赖，理论上向后兼容 2025.x。若你版本更早且有差异请提 issue。

## 协议与开发

- 组件中的 `_async_handle_message(self, user_input, chat_log)` 必须收两个参数（HA 2026.8+）。`_async_handle_message` 调用 `chat_log.async_provide_llm_data()`（HA/Claw 在这里注入工具），随后工具循环内用 aiohttp 直连 `/chat/completions` 并解析 `tool_calls`，经 `chat_log.async_add_assistant_content()` 让 HA 执行工具，最后由 `conversation.async_get_result_from_chat_log()` 产出最终结果。这是 v2.0.0 起的「协议合规大脑」写法。
- 品牌图标由 `make_icon.py` 生成（纯标准库，无第三方依赖），位于 `brand/icon.png`。
- 本仓库同时附带一个独立小集成 [`llm_assist_compat`](custom_components/llm_assist_compat/)，用途见下节。

---

## 附带集成：`llm_assist_compat`（AssistAPI 兼容层）

### 它解决什么

- HA **≤ 2026.7** 时代，`homeassistant.helpers.llm` 里定义有 `class AssistAPI`，被 **Claw Assistant** 等旧协议组件在启动时打 patch 使用。
- HA **2026.8** 重构了 LLM 协议（改为 `async_register_api` + `async_get_apis` 注册制），从 `helpers.llm` **删除**了 `AssistAPI`，导致仍按其旧接口挂载的组件 `AttributeError: module 'homeassistant.helpers.llm' has no attribute 'AssistAPI'`，启动直接失败。
- 本集成所做的唯一事情：在加载时把 `AssistAPI` 以一个**静态兼容桩**补回 `llm` 模块，让 Claw 等旧组件的快照/打 patch 不再崩。（2026.8 的 assist 走的是新协议，并不真正调用这个类，所以桩方法只需“存在且可调用”。）

### 安装

把 `custom_components/llm_assist_compat/` 整个目录随本组件一起放进 HA 的 `custom_components/` 下，重启即可。

### 让它在 Claw 之前生效（关键）

`config_flow: false` 的集成，HA 默认不加载、独立创建也不保证时序。要让注入在 Claw 之前跑，任选一种**可靠**方式：

1. **在 `configuration.yaml` 声明（推荐）**：
   ```yaml
   llm_assist_compat:
   ```
   HA 会在初始化早期加载它并执行注入。

2. **在 Claw 的 `manifest.json` 里把本次定义为依赖**，把 `after_dependencies` 追加 `llm_assist_compat`：
   ```json
   "after_dependencies": ["assist_pipeline", "llm_assist_compat"]
   ```

3. **最简单省事（无需本集成）**：直接在 Claw 的 `runtime/llm/internal_llm.py` 里，`from homeassistant.helpers import llm` 之后插入以下桩（Claw 更新后需重新加）：
   ```python
   if not hasattr(llm, "AssistAPI"):
       class _AssistCompat:
           def __init__(self, hass=None):
               self.hass = hass
           @staticmethod
           def _async_get_api_prompt(_ctx, _exposed=None) -> str:
               return ""
           @staticmethod
           def _async_get_tools(_ctx, _exposed=None):
               return []
           @staticmethod
           async def async_get_api_instance(_ctx):
               return None
       llm.AssistAPI = _AssistCompat
   ```

> 前提：你的 HA 必须是 **2026.8**（`AssistAPI` 被删的那版）。旧版 HA 自带你无需本集成。

## License

[MIT](LICENSE)