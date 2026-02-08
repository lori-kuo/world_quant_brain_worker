# AI Desktop Assistant

这是一个简单的桌面助手应用，模仿“豆包”的体验，允许用户截取屏幕并与 AI 进行对话。

## 功能
- **截屏提问 (Snip & Chat)**: 点击按钮，截取当前全屏，并自动打开聊天窗口发送给 AI。
- **纯文本对话**: 直接与 AI 聊天。

## 安装与配置

1.  **安装依赖**:
    确保你已经安装了 Python。在终端中运行以下命令安装所需库：
    ```bash
    pip install -r requirements.txt
    ```

2.  **配置 API**:
    打开 `config.json` 文件，确认你的 API Key 和 Base URL 配置正确。
    ```json
    {
        "api_key": "你的API_KEY",
        "base_url": "https://api.moonshot.cn/v1",
        "model": "kimi-k2-turbo-preview"
    }
    ```
    *注意*: 如果使用的模型不支持直接图片输入（Vision），API 可能会报错。如果遇到这种情况，请尝试更换支持 Vision 的模型，或者仅使用文本功能。

## 运行

双击 `run.bat` 或在终端运行：
```bash
python main.py
```

## 未来计划
- 支持实时语音对话。
- 支持局部区域截屏（目前为全屏）。
- 优化图片上传逻辑（适配 Moonshot 文件上传 API）。
