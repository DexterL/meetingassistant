# ASR 准确率调优计划

## 1. 当前结论

当前最初效果差的主要原因是使用了链路验证配置：

```json
{
  "model": "tiny",
  "device": "cpu",
  "compute_type": "int8"
}
```

`tiny` 适合快速验证系统链路，不适合作为会议转写准确率基线。

已完成一次路线 1 验证：将本地配置切换到 `small`，并启用 `beam_size`、VAD、固定中文和 `initial_prompt` 后，60 秒样例的识别质量明显提升，已经能读出会议大意。

## 2. 当前 faster-whisper 参数

建议准确率优先配置：

```json
{
  "asr": {
    "provider": "faster_whisper",
    "model": "small",
    "device": "cpu",
    "compute_type": "int8",
    "language": "zh",
    "beam_size": 5,
    "best_of": 5,
    "temperature": 0,
    "vad_filter": true,
    "vad_parameters": {
      "min_silence_duration_ms": 500
    },
    "condition_on_previous_text": true,
    "initial_prompt": "以下是普通话会议录音，请使用简体中文输出，保留专有名词、人名、项目名和数字。"
  }
}
```

说明：

- `model`: 优先从 `small` 起步，再评估 `medium`、`large-v3`。
- `beam_size`: 提高搜索质量，速度会下降。
- `vad_filter`: 过滤静音和非语音段，长录音更稳。
- `initial_prompt`: 用于加入会议主题、专有名词、人名、项目名。
- `condition_on_previous_text`: 保持上下文连续性，会议长段落更有帮助。

## 3. 推荐试验顺序

### 第一步：完善术语提示

由用户提供：

- 会议主题。
- 常见人名。
- 项目名。
- 产品名。
- 公司内部术语。
- 英文缩写。

将这些内容加入 `initial_prompt`。

### 第二步：模型尺寸对比

同一段 60 秒音频，按以下顺序测试：

1. `small`
2. `medium`
3. `large-v3`
4. `turbo`

记录：

- 转写耗时。
- 关键术语是否正确。
- 大意是否可读。
- 是否出现明显幻听或错字。

### 第三步：确定开发默认配置

开发机上建议默认使用：

- `small`：速度和效果折中。
- `medium`：如果本机可接受等待时间。

实际双 5090 内网环境建议验证：

- `large-v3`
- `turbo`
- 中文专项 ASR 模型。

## 4. 需要用户配合

请提供一份术语清单，格式可以很简单：

```text
会议主题：
人名：
项目名：
产品名：
公司内部术语：
英文缩写：
```

同时建议提供一段 1-3 分钟的人工校对转写，用于评估不同模型的准确率。

## 5. 下一步工程动作

- 增加一个 ASR 对比脚本，自动对同一音频跑不同模型。
- 输出不同模型的转写文件，例如：
  - `data/transcripts/讨论音频样例-60s.small.md`
  - `data/transcripts/讨论音频样例-60s.medium.md`
  - `data/transcripts/讨论音频样例-60s.large-v3.md`
- 在 Web 页面显示当前使用的 ASR 模型和参数。

