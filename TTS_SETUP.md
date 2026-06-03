# TCF 口语真人 TTS 付费与绑定说明

## 推荐路线

优先用 ElevenLabs：法语声音自然，适合背诵模板和做 shadowing。备用用 OpenAI TTS：接口简单，适合自己写脚本批量生成音频。

## ElevenLabs

1. 打开 https://elevenlabs.io/pricing 注册并选择套餐。
2. 打开 https://elevenlabs.io/app/settings/api-keys 创建 API key。
3. 打开 https://elevenlabs.io/app/voice-library 选择声音，复制 `voice_id`。
4. 打开本项目的 `index.html`，在右侧选择 ElevenLabs，填入 API key 和 `voice_id`，点击“保存绑定”。
5. 点击任意模板卡片的“朗读”测试。

## OpenAI TTS

1. 打开 https://platform.openai.com/settings/organization/billing/overview 绑定付款方式。
2. 打开 https://platform.openai.com/api-keys 创建 API key。
3. 打开本项目的 `index.html`，右侧选择 OpenAI TTS，填入 API key，选择 `marin` 或 `cedar` 声音，点击“保存绑定”。
4. 点击“测试朗读”或模板卡片“朗读”。

## 注意

- OpenAI API 和 ChatGPT Plus 是分开计费的。
- API key 是密码级别的凭证，只适合本机练习，不要发给别人。
- 如果浏览器阻止网页直接请求 API，可以把模板文本复制到 ElevenLabs 或 OpenAI 控制台生成音频。
