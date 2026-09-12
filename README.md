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

| 字段      | 说明                                                                   |
|-----------|------------------------------------------------------------------------|
| Name      | 集成显示名，例如「火山方舟」                                             |
| Base URL  | OpenAI 兼容的 API 根地址，默认火山方舟 `…/api/v3`，末尾**不带** `/chat/completions` |
| API Key   | 你的服务商 API Key                                                     |
| Model     | 模型 / 接入点 ID（火山方舟用 `ep-…` 或模型名，详见下方排查）               |

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

- 组件中的 `_async_handle_message(self, user_input, chat_log)` 必须收两个参数（HA 2026.8+），响应用 `intent.IntentResponse` + `async_set_speech`，并需 `async_add_assistant_content_without_tools` 回写历史。
- 品牌图标由 `make_icon.py` 生成（纯标准库，无第三方依赖），位于 `brand/icon.png`。

## License

[MIT](LICENSE)