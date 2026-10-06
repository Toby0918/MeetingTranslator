# MeetingTranslator · 会议实时翻译

Windows 10/11 64 位桌面英语 → 中文字幕工具。声音由本机 Whisper small.en 识别，默认由本地模型翻译；可手动切换到 DeepSeek 增强翻译。支持电脑会议声音、现场麦克风、中英字幕、置顶悬浮窗和手动导出记录。

## 下载后使用

从 [GitHub Releases](https://github.com/Toby0918/MeetingTranslator/releases/latest) 下载 `MeetingTranslator-1.0.0-Windows-x64.zip`。这是私有仓库，需要登录有访问权限的 GitHub 账号。

完整解压后打开 `MeetingTranslator` 文件夹，双击 `MeetingTranslator.exe`。程序自带 Python、依赖和两套模型，不需要安装 Python、运行命令或首次联网下载模型。请保留旁边的 `_internal`、`models` 和 `licenses` 文件夹；不要只复制 EXE，也不要在压缩包预览中直接运行。

程序默认选择“本地翻译（免费）”。选择“电脑会议声音”，并选中与会议软件一致的耳机或扬声器，点击“开始翻译”。若翻译现场英语，选择“麦克风（现场英语）”和对应麦克风。切换输入或翻译模式前先停止。停顿后显示字幕，连续讲话通常最多约 12 秒分段；复杂长句可能产生较长等待。

“悬浮字幕”可显示置顶双语窗口。“导出记录”手动保存当前字幕。正常使用不自动保存音频或字幕；关闭前请导出需要保留的文字。

## 可选 DeepSeek 增强翻译

选择“DeepSeek 增强翻译”，点击“设置 API 密钥”，在程序内输入自己的 DeepSeek API 密钥。界面输入的密钥只保留在本次进程内存中，关闭后清除；也支持 `DEEPSEEK_API_KEY` 环境变量。安装包和仓库均不含作者的个人密钥或密钥来源配置。

增强模式仅将识别文字和有限前文发送到 DeepSeek 官方接口，音频在本机处理。该模式需要网络和自己的 API 余额。接口超时或失败会保留英文并明确提示，用户可停止后手动切回本地模式。

## 本版改进与验证

离线翻译按句处理较长字幕，避免单句翻译模型遗漏后续句子；对明确的英文单词计数和少量习语做保守处理；不可读译文会尝试另一种本地解码，仍失败则明确提示。长音频到达时长上限时优先寻找最近的短暂停顿，剩余音频进入下一段，不直接丢弃。

五段 TED 的改进前后结果、AI 对照方法和限制见 [评估报告](docs/TED评估报告_2026-10-06.md)。独立运行包验证见仓库中的 [发布验证](https://github.com/Toby0918/MeetingTranslator/blob/main/docs/release-verification.json)。这些验证不替代真实多人会议验收，尤其应核对人名、数字、单位、否定和专业词汇。

## 下载包自检

在解压后的文件夹中打开 PowerShell，可运行以下可选诊断。自检创建界面、加载本地模型并枚举设备，保存报告，不开始声音采集。

```powershell
.\MeetingTranslator.exe --self-test .\self-test.json
```

报告中 `passed` 为 `true` 表示这些检查通过。有音频文件时，可加 `--audio "测试音频.wav"` 验证该文件的识别和本地翻译。诊断需要当前用户具有写入报告路径的权限。

## 开发与重建

源码位于 `app/`，测试位于 `tests/`。完整重建需要 Windows x64 和 Python 3.12。模型须位于项目 `models/` 中，或在不提交的 `runtime-config.json` 中设置 `model_root`。

| 模型 | 存放位置 | 来源 |
| --- | --- | --- |
| Whisper small.en | `models/whisper-small.en/` | [SYSTRAN 转换模型](https://huggingface.co/Systran/faster-whisper-small.en) |
| Argos 英语 → 中文 1.9 | `models/translation/translate-en_zh-1_9/` | [官方模型包](https://argos-net.com/v1/translate-en_zh-1_9.argosmodel)，解压到 translation 目录 |

```powershell
python -m venv .build-venv
.\.build-venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.build-venv\Scripts\python.exe run_tests.py
.\.build-venv\Scripts\python.exe scripts/build_windows.py --models .\models
```

产物位于 `dist/`，包含完整 ZIP、文件清单和 `SHA256SUMS.txt`。模型、运行环境、录音、TED 源素材和个人配置不进入 Git；发布 ZIP 单独作为 Release 附件上传。重跑 TED 评估见 `scripts/evaluate_ted.py --help`。

## 系统条件

目前提供 Windows 10/11 x64 的 CPU 版本，未启用 CUDA。需要正常可用的播放设备或麦克风，以及足够内存和磁盘空间容纳完整运行环境与模型。实际速度取决于电脑和讲话方式。本次验证使用 i7-13700K；未对所有 CPU、Windows 版本或多人会议软件进行兼容性验证。

软件当前未进行商业代码签名，Windows 可能提示未知发布者。只从此仓库的 Release 下载，并可核对同页 `SHA256SUMS.txt`。第三方模型和依赖的来源、授权及署名见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和随包 `licenses/`。
