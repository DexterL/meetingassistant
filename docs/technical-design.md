# 会议助手技术设计文档（聚焦版）

## 1. 当前目标

现阶段只实现并验证以下功能：

| 编号 | 功能 | 当前目标 |
| --- | --- | --- |
| F1 | 音频上传 | 支持上传或放入本地会议音频文件。 |
| F3 | 语音识别 | 将音频转写为文字稿。 |
| F4 | 可选说话人分离 | 在可行时标注不同发言人；不可行时先保留时间戳。 |
| F5 | 文本规整 | 将 ASR 转写稿整理为更清晰、少口语化、少重复的会议记录。 |
| F6 | 会议提要 | 基于规整后的会议记录生成内容提要。 |

## 2. 核心约束

- 系统运行在封闭内网电脑上，正常运行不依赖外网服务。
- 底层存储只使用本地文件系统。
- 开发阶段可使用本地小参数模型验证功能。
- 实际内网环境可通过配置切换到大规模 LLM，不修改业务代码。
- 处理实验数据不得上传到 Git 仓库。

## 3. 本地文件结构

```text
data/
  audio/
    <meeting_id>.<ext>
  transcripts/
    <meeting_id>.md
  summaries/
    <meeting_id>.md
```

目录说明：

- `data/audio/`：原始会议音频。
- `data/transcripts/`：ASR 原始转写稿。
- `data/summaries/`：整理后的会议记录与总结。

当前 `.gitignore` 会忽略 `data/` 下所有真实数据，只保留 `.gitkeep`。

## 4. 总体架构

```text
用户浏览器
  |
  v
Web 前端
  |
  v
后端 API 服务
  |
  +--> 本地文件系统
  |     +--> data/audio/
  |     +--> data/transcripts/
  |     +--> data/summaries/
  |
  +--> ASRClient
  |
  +--> LLMClient

本地模型服务
  |
  +--> ASR 服务
  +--> LLM 服务
```

MVP 采用单机处理：上传音频后，按顺序执行 ASR、文本规整、内容提要生成。说话人分离保留为可选能力，不作为当前推进阻塞项。存储上只保留 `audio`、`transcripts`、`summaries` 三个独立目录。

## 5. 处理流程

### 5.1 音频上传

1. 用户上传音频文件。
2. 后端生成 `meeting_id`。
3. 文件保存到 `data/audio/<meeting_id>.<ext>`。
4. 页面显示该音频已可处理。

支持格式先以常见文件为主：

- `.m4a`
- `.mp3`
- `.wav`
- `.flac`

### 5.2 语音识别

1. 后端读取 `data/audio/<meeting_id>.<ext>`。
2. 调用 `ASRClient.transcribe(audio_path, options)`。
3. 生成基础转写内容。
4. 保存到 `data/transcripts/<meeting_id>.md`。

转写稿建议格式：

```markdown
# 会议转写稿

音频文件：讨论音频样例.m4a
识别模型：<asr_model>

## 原始转写

[00:00:01 - 00:00:08] 这里是识别出来的文本。
[00:00:09 - 00:00:16] 这里是下一段文本。
```

### 5.3 可选说话人分离（当前暂缓）

说话人分离作为可选能力，不阻塞主流程。当前阶段允许跳过 F4，直接进入 F5 文本规整。

若模型支持说话人分离，转写稿格式为：

```markdown
[00:00:01 - 00:00:08] Speaker 1：这里是识别出来的文本。
[00:00:09 - 00:00:16] Speaker 2：这里是下一段文本。
```

若暂不支持，则只保留时间戳：

```markdown
[00:00:01 - 00:00:08] 这里是识别出来的文本。
```

### 5.4 文本规整

规整输入来自 ASR 转写稿。规整目标：

- 删除明显语气词、重复、口头禅。
- 修正明显口误。
- 保留原始语义，不新增事实。
- 保留关键数字、名称、日期、术语。
- 尽量保持会议讨论顺序。

规整后的内容写入 `data/summaries/<meeting_id>.md`，不回写 `data/transcripts/`。

```markdown
# 会议记录

来源转写稿：<meeting_id>.md
整理模型：<llm_model>

## 整理内容

...
```

### 5.5 会议内容提要

提要输入来自整理后的会议记录。提要目标：

- 按议题归纳主要讨论内容。
- 保持中立客观。
- 不补充原文不存在的信息。

输出仍保存到 `data/summaries/<meeting_id>.md`。第三类目录只保存最终文字成果，不再拆出额外目录。

建议格式：

```markdown
# 会议内容提要

## 议题一：<议题名称>

- 讨论了……
- 提到了……

## 议题二：<议题名称>

- 讨论了……
- 提到了……
```

## 6. 模型配置设计

模型选择必须可配置。开发阶段可用小模型，实际部署阶段可切换到更大模型或中文专项模型。

示例配置：

```yaml
llm:
  provider: openai_compatible
  base_url: "http://127.0.0.1:11434/v1"
  api_key: "local"
  model: "qwen2.5:7b"
  temperature: 0.2
  max_tokens: 4096

asr:
  provider: "faster_whisper"
  model: "small"
  device: "auto"
  compute_type: "default"
  language: "zh"
  beam_size: 5
  best_of: 5
  temperature: 0
  vad_filter: true
  vad_parameters:
    min_silence_duration_ms: 500
  condition_on_previous_text: true
  initial_prompt: "以下是普通话会议录音，请使用简体中文输出，保留专有名词、人名、项目名和数字。"
  enable_diarization: false
```

实际内网环境只改配置即可切换模型档位：

```yaml
asr:
  provider: "faster_whisper"
  model: "large-v3"
  device: "cuda"
  compute_type: "float16"
  language: "zh"
  beam_size: 5
  vad_filter: true
```

LLM 同样通过配置切换：

```yaml
llm:
  provider: openai_compatible
  base_url: "http://内网LLM服务地址:8000/v1"
  api_key: "local"
  model: "Qwen3-32B-Instruct"
  temperature: 0.2
  max_tokens: 8192
```

后端只依赖抽象接口：

- `ASRClient.transcribe(audio_path, options)`
- `LLMClient.clean_transcript(transcript, options)`
- `LLMClient.generate_topic_summary(cleaned_transcript, options)`

ASR 选型和参数逻辑详见 [ASR 模型选型与参数配置说明](asr-tuning-plan.md)。

说话人分离的需求判断详见 [说话人分离需求分析与当前决策](diarization-decision.md)。

## 7. API 草案

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/audio` | 上传音频，保存到 `data/audio/` |
| GET | `/api/files` | 获取本地音频、转写稿、提要文件列表 |
| POST | `/api/transcribe/{meeting_id}` | 对音频执行语音识别 |
| POST | `/api/clean/{meeting_id}` | 对转写稿执行文本规整，结果写入 `data/summaries/` |
| POST | `/api/summarize/{meeting_id}` | 对整理后的会议记录生成会议内容提要 |
| POST | `/api/process/{meeting_id}` | 顺序执行转写、规整、提要 |
| GET | `/api/transcripts/{meeting_id}` | 读取 ASR 原始转写稿 |
| GET | `/api/summaries/{meeting_id}` | 读取整理后的会议记录与总结 |

## 8. 分阶段实现计划

### 阶段一：文件上传与目录闭环

- 实现 `data/audio/`、`data/transcripts/`、`data/summaries/` 目录。
- 实现音频上传。
- 实现本地文件列表展示。
- 确认样例音频不会进入 Git。

验收标准：

- `data/audio/讨论音频样例.m4a` 存在且被 Git 忽略。
- 前端或接口能列出本地音频文件。

### 阶段二：ASR 转写

- 接入本地 ASR。
- 对样例音频生成 `data/transcripts/<meeting_id>.md`。

验收标准：

- 样例音频可以生成可读转写稿。
- 转写稿被 Git 忽略。

### 阶段三：说话人分离决策

当前决策：暂缓 F4，不作为下一阶段开发任务。

原因：

- 当前 ASR 转写效果已经满足进入文本规整的前置条件。
- 说话人分离需要额外模型或 provider，会引入新的依赖和离线部署问题。
- 当前目标更关注会议记录规整和内容提要，先推进 F5/F6 更快产生业务价值。

保留策略：

- 配置中继续保留 `enable_diarization`。
- 转写稿格式继续兼容 `Speaker N`。
- 后续如果明确需要“谁说了什么”，再单独评估 pyannote、FunASR 或其他方案。

验收标准：

- 关闭或不实现说话人分离时，ASR、文本规整、会议提要流程不受影响。

### 阶段四：文本规整（进行中）

- 接入本地小参数 LLM。
- 实现 `LLMClient.clean_transcript`。
- 将整理后的会议记录写入 `data/summaries/<meeting_id>.md`。
- 先使用 OpenAI-compatible 本地 LLM 服务，保持后续模型可配置切换。

验收标准：

- 规整结果比原始 ASR 更适合阅读。
- 未引入会议中不存在的新事实。
- 更换 LLM 配置不需要修改业务代码。

### 阶段五：会议内容提要

- 实现 `LLMClient.generate_topic_summary`。
- 基于 `data/summaries/<meeting_id>.md` 中的整理内容补充会议提要。
- 只生成内容提要。

验收标准：

- 提要按议题组织。
- 提要不包含原文没有的信息。
- 同一份转写稿可以通过配置切换小模型/大模型重复生成最终文字成果。

## 9. 质量评估

### ASR

- 转写是否基本可读。
- 是否保留关键名词、数字和时间。
- 长音频是否能完整处理。

### 说话人分离

- 当前暂缓，不作为进入 F5 的前置条件。
- 是否能区分主要发言人。
- 说话人标签错误是否影响阅读。
- 效果不佳时是否可以关闭。

### 文本规整

- 是否减少口语化、重复和明显口误。
- 是否保持原意。
- 是否避免新增事实。

### 内容提要

- 是否覆盖主要议题。
- 是否表达简洁。
- 是否只围绕主要议题生成内容提要。

## 10. 待确认问题

1. 当前样例音频主要是普通话，还是存在中英混合？
2. 单个音频典型时长和最长时长是多少？
3. F4 暂缓后，是否接受转写稿仅保留时间戳、不标注发言人？
4. 会议内容提要是否按“议题”组织即可，是否需要固定模板？

## 11. 参考资料

- faster-whisper 官方仓库：https://github.com/SYSTRAN/faster-whisper
- OpenAI Whisper 官方仓库：https://github.com/openai/whisper
- pyannote.audio 论文：https://arxiv.org/abs/1911.01255
- FunASR 论文：https://arxiv.org/abs/2305.11013
