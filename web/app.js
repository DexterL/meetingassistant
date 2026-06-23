const audioList = document.querySelector("#audioList");
const transcriptList = document.querySelector("#transcriptList");
const summaryList = document.querySelector("#summaryList");
const audioCount = document.querySelector("#audioCount");
const transcriptCount = document.querySelector("#transcriptCount");
const summaryCount = document.querySelector("#summaryCount");
const uploadForm = document.querySelector("#uploadForm");
const audioInput = document.querySelector("#audioInput");
const uploadStatus = document.querySelector("#uploadStatus");
const refreshButton = document.querySelector("#refreshButton");
const previewContent = document.querySelector("#previewContent");
const previewMeta = document.querySelector("#previewMeta");

function formatBytes(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function formatTime(seconds) {
  return new Date(seconds * 1000).toLocaleString();
}

function setStatus(message) {
  uploadStatus.textContent = message;
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `请求失败：${response.status}`);
  }
  return data;
}

function renderEmpty(target, text) {
  target.innerHTML = "";
  const empty = document.createElement("div");
  empty.className = "empty";
  empty.textContent = text;
  target.append(empty);
}

function renderAudioFiles(files) {
  audioCount.textContent = String(files.length);
  audioList.innerHTML = "";
  if (!files.length) {
    renderEmpty(audioList, "还没有音频文件。");
    return;
  }

  for (const file of files) {
    const item = document.createElement("article");
    item.className = "file-item";
    item.innerHTML = `
      <div class="file-name"></div>
      <div class="file-meta">${formatBytes(file.size)} · ${formatTime(file.updated_at)}</div>
      <div class="file-actions">
        <button type="button" data-action="transcribe">执行转写</button>
      </div>
    `;
    item.querySelector(".file-name").textContent = file.name;
    item.querySelector("[data-action='transcribe']").addEventListener("click", async () => {
      setStatus(`正在转写 ${file.name}...`);
      try {
        await requestJson(`/api/transcribe/${encodeURIComponent(file.meeting_id)}`, { method: "POST" });
        setStatus("转写稿已生成。");
        await loadFiles();
      } catch (error) {
        setStatus(error.message);
      }
    });
    audioList.append(item);
  }
}

function renderMarkdownFiles(target, countTarget, files, type) {
  countTarget.textContent = String(files.length);
  target.innerHTML = "";
  if (!files.length) {
    renderEmpty(target, type === "transcripts" ? "还没有转写稿。" : "还没有内容提要。");
    return;
  }

  for (const file of files) {
    const item = document.createElement("article");
    item.className = "file-item";
    item.innerHTML = `
      <div class="file-name"></div>
      <div class="file-meta">${formatBytes(file.size)} · ${formatTime(file.updated_at)}</div>
      <div class="file-actions">
        <button class="secondary" type="button" data-action="preview">预览</button>
      </div>
    `;
    item.querySelector(".file-name").textContent = file.name;
    item.querySelector("[data-action='preview']").addEventListener("click", async () => {
      const endpoint = type === "transcripts" ? "transcripts" : "summaries";
      try {
        const data = await requestJson(`/api/${endpoint}/${encodeURIComponent(file.meeting_id)}`);
        previewMeta.textContent = file.name;
        previewContent.textContent = data.content;
      } catch (error) {
        previewMeta.textContent = "读取失败";
        previewContent.textContent = error.message;
      }
    });
    target.append(item);
  }
}

async function loadFiles() {
  const files = await requestJson("/api/files");
  renderAudioFiles(files.audio);
  renderMarkdownFiles(transcriptList, transcriptCount, files.transcripts, "transcripts");
  renderMarkdownFiles(summaryList, summaryCount, files.summaries, "summaries");
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = audioInput.files[0];
  if (!file) {
    setStatus("请选择一个音频文件。");
    return;
  }

  setStatus(`正在上传 ${file.name}...`);
  try {
    await requestJson(`/api/audio?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    });
    audioInput.value = "";
    setStatus("音频已上传。");
    await loadFiles();
  } catch (error) {
    setStatus(error.message);
  }
});

refreshButton.addEventListener("click", () => {
  loadFiles().catch((error) => setStatus(error.message));
});

loadFiles().catch((error) => setStatus(error.message));
