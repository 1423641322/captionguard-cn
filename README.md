# CaptionGuard CN

[English README](README_EN.md)

CaptionGuard CN 是一个面向 Adobe Premiere Pro、中文优化且支持多语言的本地字幕工作台。当前仓库包含：

- `plugin/`：Premiere Pro 25.6+ 的 UXP 面板；
- `backend/`：仅监听本机的 Python 转写服务；
- `tests/`：语言感知断句、术语替换、低置信度标记和 SRT 输出测试。

当前 MVP 已打通以下流程：

1. 读取 Premiere 当前活动序列、音频轨数量与入出点；
2. 使用用户选择的 Adobe Media Encoder `.epr` 音频预设，将完整序列或入出点范围导出到插件临时目录；
3. 自动把导出的音频发送到本机服务，也可手动选择已有音频；
4. 使用 `faster-whisper` 生成带时间戳的字幕；
5. 应用术语表、语言感知断句和低置信度标记；
6. 在面板预览并保存 `.srt` 文件。

语言能力：

- 可以手动选择 Whisper 支持的全部 100 种语言；
- “自动检测（多语言）”会在不同音频片段重新判断语言；
- “中文 + English 混合增强”针对代码切换内容启用逐片段语言检测和双语提示；
- 自动字幕长度会按语言调整：中文 20、英文及多数空格分词语言 42、中英混合 32；
- 英文字幕优先在句号、问号、分号和单词边界处断句，并保留正确空格。

## 普通用户：只下载 EXE（推荐）

普通用户只需下载并运行发布版 `CaptionGuard-CN.exe`，不需要另外安装 Python，也不需要
UXP Developer Tool。EXE 同时包含本地转写服务和 Premiere UXP 插件安装包，运行后会常驻
Windows 系统托盘。

1. 从 [GitHub Releases](https://github.com/1423641322/captionguard-cn/releases/latest) 下载并运行 `CaptionGuard-CN.exe`；
2. 在 Windows 右下角系统托盘找到 CaptionGuard 图标；
3. 右键图标，选择“安装 Premiere 插件”；
4. 在 Creative Cloud Desktop 弹出的窗口中确认安装；
5. 重启 Premiere，然后进入“窗口 → UXP 插件 → CaptionGuard CN”；
6. 使用插件期间保持 `CaptionGuard-CN.exe` 在后台运行。

首次选择 Whisper 模型进行转写时需要联网下载模型；下载完成后，后续识别可以在本机运行。
右键系统托盘中的 CaptionGuard 图标，可以检查服务、重新安装 Premiere 插件、启用登录后
自动启动或退出。软件升级后如果面板没有同步更新，请从托盘菜单重新安装插件。

CaptionGuard 由两个需要同时工作的部分组成：Premiere 中的 UXP 面板负责操作界面，EXE
负责本地转写。因此即使面板已经安装，转写期间也必须保持 EXE 或开发版 Python 服务运行。

## 环境要求

- Windows 10/11
- Adobe Premiere Pro 25.6+
- Adobe Creative Cloud Desktop（安装发布版插件时使用）
- 首次下载 Whisper 模型时需要网络连接

源码开发还需要 Python 3.11+ 和 UXP Developer Tool 2.2+。

## 启动本地服务

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,asr]"
captionguard-server
```

首次转写时会下载所选的 Whisper 模型。服务默认只监听 `127.0.0.1:8765`，健康检查地址为 `http://127.0.0.1:8765/health`。

如只想运行不依赖模型的单元测试：

```powershell
python -m pip install -e ".[dev]"
pytest
node --test plugin/tests/timeline.test.js
```

## 开发者：通过 UXP Developer Tool 加载

也可以不安装发布版 `.ccx`，直接在 UXP Developer Tool 中加载 `plugin/` 源码进行开发和
调试。UXP Developer Tool 只负责加载面板，仍然需要 EXE 或 Python 本地服务提供转写能力。

1. 在 Premiere 的“设置 → 插件”中启用开发者模式，并重启 Premiere；
2. 在 UXP Developer Tool 中选择 **Add Plugin**，打开 `plugin/manifest.json`；
3. 点击 **Load & Watch**；
4. 在 Premiere 的“窗口 → UXP 插件”中打开 **CaptionGuard CN**；
5. 运行 `CaptionGuard-CN.exe`，或按照上一节命令启动 Python 本地服务；
6. 在面板中点击“检查本地服务”；
7. 首次使用时选择一个只导出音频的 Adobe Media Encoder `.epr` 预设；
8. 在 Premiere 中设置入点和出点，然后点击“导出时间线并转写”。未设置有效入出点时会导出完整序列。

不要同时安装发布版 CCX 和加载同一个开发版插件。二者使用相同的插件 ID，可能导致重复面板
或加载冲突。切换到开发模式前，请先在 Creative Cloud Desktop 中卸载发布版插件；切换回
发布版时，请先在 UXP Developer Tool 中卸载开发版。

修改 `manifest.json` 后，需要在 UXP Developer Tool 中卸载再重新加载插件。

## 构建 Windows 发布版

运行完整构建脚本：

```powershell
.\scripts\build_release.ps1
```

脚本会先根据 `plugin/` 生成 `.ccx`，再将独立的 Python 3.12 运行环境、本地转写服务和插件安装包封装进一个 Windows 启动程序。输出文件为 `dist/CaptionGuard-CN.exe`，`.ccx` 已内置，无需随 EXE 单独分发。首次运行会把运行组件释放到当前用户的本地应用目录。发布前也可以使用 UXP Developer Tool 的 **Package** 功能重新生成并验证 `dist/ccx/` 中的包。

## 当前限制

- 当前按序列混音结果导出，尚未支持只选择指定音频轨；
- 生成的是标准 SRT，需要手动导入 Premiere；
- 本地服务目前使用 HTTP，只适合 Windows 本机开发；macOS 版需要本机 HTTPS 或原生桥接；
- 增量重识别与人工修改保护将在下一阶段加入。

## API

### `GET /health`

返回本地服务状态。

### `POST /v1/transcriptions`

`multipart/form-data` 字段：

- `file`：音频文件；
- `language`：`auto`、`zh`、`en` 等；
- `model_size`：默认 `small`；
- `max_chars`：单条字幕最大字符数；
- `confidence_threshold`：低置信度阈值；
- `glossary_json`：JSON 对象，例如 `{"Open AI":"OpenAI"}`。

响应包含标准化字幕片段、低置信度问题列表和完整 SRT。

使用 `GET /v1/languages` 可以读取当前界面支持的全部 Whisper 语言。`language=zh-en`
启用中英混合增强模式；`max_chars=0` 会根据语言自动选择字幕长度。

## 许可证

Apache-2.0。模型与 FFmpeg 使用各自许可证。
