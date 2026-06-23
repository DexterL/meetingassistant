# Meeting Assistant

本项目当前聚焦本地会议音频处理的最小闭环：

- F1 音频上传
- F3 语音识别
- F4 可选说话人分离
- F5 文本规整
- F6 会议提要

## 本地运行

当前实现使用 Python 标准库，不需要安装后端依赖。

```bash
python3 -m app.server
```

打开：

```text
http://127.0.0.1:8765
```

## 数据目录

```text
data/audio/        原始会议音频
data/transcripts/  ASR 转写稿和规整后的会议记录
data/summaries/    会议内容提要
```

`data/` 下真实数据会被 `.gitignore` 忽略，只提交 `.gitkeep` 保留目录。

## 当前状态

已实现阶段一：

- 本地 Web 页面
- 音频上传
- 本地文件列表
- 转写稿和内容提要预览
- 占位处理接口，为后续 ASR/LLM 接入保留流程

## ASR 配置

安装本地 ASR 依赖：

```bash
brew install ffmpeg
uv venv --python /Users/dexterl/.local/bin/python3.11 .venv
uv pip install --python .venv/bin/python faster-whisper
```

复制示例配置后按本机模型环境调整：

```bash
cp config/app.example.json config/app.json
```

当前代码优先支持 `faster-whisper`。未安装本地 ASR 依赖时，转写接口会返回明确错误，不会调用外网服务。

安装依赖后可直接用脚本转写：

```bash
.venv/bin/python scripts/transcribe_audio.py 讨论音频样例
```
