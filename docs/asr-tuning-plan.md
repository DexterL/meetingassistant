# ASR 模型选型与参数配置说明

## 1. 选型目标

当前 ASR 只服务于聚焦阶段的 F3/F4/F5/F6：

- 将会议音频转成可读文字稿。
- 尽量保留时间戳。
- 为后续文本规整和会议提要提供输入。
- 说话人分离作为可选能力，当前暂缓，不阻塞 F5 文本规整。

选型优先级：

1. 可以在封闭内网离线运行。
2. 可以通过配置切换模型，不改业务流程。
3. 中文普通话会议效果可接受。
4. 支持长音频处理。
5. 开发机可用小模型验证，实际环境可切大模型。

## 2. 当前方案：faster-whisper

当前默认 provider 是：

```json
{
  "provider": "faster_whisper"
}
```

选择原因：

- 本地部署简单，已经在当前项目虚拟环境验证可运行。
- 支持 Whisper 系列多个模型档位。
- 支持 `beam_size`、VAD、固定语言、提示词等关键参数。
- 输出片段带时间戳，适合保存为会议转写稿。
- 后续仍可保留 `ASRClient` 抽象，切换到 FunASR 或其他中文专项 ASR。

## 3. 当前验证结论

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

但 `small` 仍不是最终准确率上限。它适合作为开发阶段默认模型，实际环境应继续评估 `medium`、`large-v3` 或中文专项 ASR。

## 4. 模型档位选择逻辑

| 模型 | 使用场景 | 优点 | 风险 |
| --- | --- | --- | --- |
| `tiny` | 只验证链路 | 速度快，下载小 | 准确率差，不适合会议转写 |
| `base` | 快速粗测 | 比 tiny 略好 | 对中文会议仍可能不足 |
| `small` | 当前开发默认 | 本机 CPU 可跑，质量明显提升 | 专有名词仍容易错 |
| `medium` | 准确率优先开发验证 | 中文效果通常更好 | CPU 较慢 |
| `large-v3` | 实际环境质量优先 | Whisper 路线质量上限更高 | 资源消耗大 |
| `turbo` | 实际环境速度/质量折中 | 比 large-v3 快 | 准确率可能略低于 large-v3 |

推荐策略：

- 开发机：`small` 起步，必要时用短片段评估 `medium`。
- 实际双 5090 内网环境：优先评估 `large-v3` 和 `turbo`。
- 中文会议准确率仍不满足时：引入 FunASR 或其他中文专项 ASR 作为第二 provider。

## 5. 当前 faster-whisper 参数

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

## 6. 参数配置逻辑

### `model`

控制模型尺寸，是影响准确率的第一因素。不要用 `tiny` 判断方案质量。

推荐：

- 默认开发：`small`
- 质量验证：`medium`
- 实际高算力：`large-v3` 或 `turbo`

### `device`

控制推理设备。

- `cpu`：开发机稳定，但慢。
- `cuda`：实际双 5090 环境优先使用。
- `auto`：由 faster-whisper 自行判断，适合通用示例配置。

### `compute_type`

控制计算精度和性能。

- `int8`：CPU 友好，速度和内存占用较好，精度可能略受影响。
- `float16`：GPU 常用，适合实际 CUDA 环境。
- `default`：交给后端决定。

建议：

- 开发 CPU：`int8`
- GPU 环境：优先测试 `float16`

### `language`

当前固定为：

```json
"language": "zh"
```

原因：会议主要面向中文场景，固定语言可以减少自动语言识别漂移。

### `beam_size`

控制解码搜索宽度。

- 值越大，通常准确率更好。
- 值越大，速度越慢。

当前建议：

```json
"beam_size": 5
```

### `best_of`

用于采样候选数量。与 `beam_size` 一起提高候选质量，速度会下降。

当前建议：

```json
"best_of": 5
```

### `temperature`

当前建议：

```json
"temperature": 0
```

原因：会议转写不需要创造性，优先稳定、确定的输出。

### `vad_filter`

控制是否启用语音活动检测。

当前建议：

```json
"vad_filter": true
```

原因：

- 长会议常有停顿、空白、环境声。
- VAD 可以减少非语音片段干扰。

### `vad_parameters`

当前建议：

```json
"vad_parameters": {
  "min_silence_duration_ms": 500
}
```

含义：将较短停顿作为切分依据，帮助会议音频形成更合理的片段。

### `condition_on_previous_text`

当前建议：

```json
"condition_on_previous_text": true
```

原因：会议内容前后关联强，启用上下文有助于提高连续段落一致性。

风险：如果前文识别严重错误，可能把错误带到后文。后续可在长音频分段策略中再评估。

### `initial_prompt`

当前通用 prompt：

```json
"initial_prompt": "以下是普通话会议录音，请使用简体中文输出，保留专有名词、人名、项目名和数字。"
```

它的作用是给模型提供领域先验。后续应加入真实术语，例如：

```text
会议主题：数据平台规划评审
人名：张三、李四
项目名：全球综合硬平台、数据集成平台
产品名：DataIntegration
公司内部术语：子工厂、硬件平台、软件模块
英文缩写：LLM、ASR、GPU
```

## 7. 推荐试验顺序

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

## 8. 后续 provider 选择

如果 faster-whisper 在 `medium` / `large-v3` 下仍不能满足中文会议要求，再引入第二条 provider：

```json
{
  "provider": "funasr"
}
```

FunASR 适合作为中文会议专项候选，尤其是需要中文标点、说话人、热词增强时。但它会引入新的模型依赖和工程适配工作，因此不作为当前第一步。

## 9. 需要用户配合

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

## 10. 下一步工程动作

- 增加一个 ASR 对比脚本，自动对同一音频跑不同模型。
- 输出不同模型的转写文件，例如：
  - `data/transcripts/讨论音频样例-60s.small.md`
  - `data/transcripts/讨论音频样例-60s.medium.md`
  - `data/transcripts/讨论音频样例-60s.large-v3.md`
- 在 Web 页面显示当前使用的 ASR 模型和参数。
