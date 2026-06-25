# 会议数据处理流程与成果物目录设计

## 1. 当前范围

现阶段只围绕以下文件流转：

- 原始音频。
- ASR 原始转写稿。
- 整理后的会议记录与总结。

## 2. 目录结构

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

## 3. 处理过程

1. 音频进入 `data/audio/`。
2. ASR 生成转写稿，写入 `data/transcripts/`。
3. 当前跳过说话人分离，保留时间戳即可；判断依据见 `docs/diarization-decision.md`。
4. LLM 基于转写稿生成整理后的会议记录与总结，写入 `data/summaries/`。

## 4. 命名建议

同一场会议使用相同 `meeting_id`：

```text
data/audio/20260623-demo.m4a
data/transcripts/20260623-demo.md
data/summaries/20260623-demo.md
```

## 5. Git 忽略策略

`data/` 下真实数据和生成结果不进入 Git，只保留 `.gitkeep`：

```gitignore
data/**
!data/
!data/**/
!data/**/.gitkeep
```

因此以下文件都会被忽略：

- `data/audio/*.m4a`
- `data/transcripts/*.md`
- `data/summaries/*.md`
