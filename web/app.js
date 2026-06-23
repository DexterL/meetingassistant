const audioList = document.querySelector("#audioList");
const audioCount = document.querySelector("#audioCount");
const uploadForm = document.querySelector("#uploadForm");
const audioInput = document.querySelector("#audioInput");
const uploadStatus = document.querySelector("#uploadStatus");
const refreshButton = document.querySelector("#refreshButton");
const activeMeeting = document.querySelector("#activeMeeting");
const progressCard = document.querySelector("#progressCard");
const progressFill = document.querySelector("#progressFill");
const jobState = document.querySelector("#jobState");
const jobStep = document.querySelector("#jobStep");
const jobMessage = document.querySelector("#jobMessage");
const previewContent = document.querySelector("#previewContent");
const previewMeta = document.querySelector("#previewMeta");
const reloadResultButton = document.querySelector("#reloadResultButton");

const stepNodes = {
  queued: document.querySelector("#stepQueued"),
  model: document.querySelector("#stepModel"),
  transcribe: document.querySelector("#stepTranscribe"),
  write: document.querySelector("#stepWrite"),
  done: document.querySelector("#stepDone"),
};

let selectedMeetingId = null;
let selectedFileName = null;
let pollTimer = null;

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

function resetSteps() {
  Object.values(stepNodes).forEach((node) => node.className = "");
}

function updateSteps(progress, state) {
  resetSteps();
  if (progress >= 5) stepNodes.queued.classList.add("is-done");
  if (progress >= 15) stepNodes.model.classList.add("is-done");
  if (progress >= 35) stepNodes.transcribe.classList.add("is-done");
  if (progress >= 85) stepNodes.write.classList.add("is-done");
  if (state === "succeeded") stepNodes.done.classList.add("is-done");
  if (state === "failed") progressCard.classList.add("is-failed");
}

function stateLabel(state) {
  return {
    idle: "未开始",
    queued: "已创建",
    running: "转换中",
    succeeded: "已完成",
    failed: "失败",
  }[state] || state;
}

function applyJob(job) {
  const progress = Number(job.progress || 0);
  progressCard.className = `progress-card is-${job.state || "idle"}`;
  progressFill.style.width = `${Math.max(0, Math.min(100, progress))}%`;
  jobState.textContent = stateLabel(job.state || "idle");
  jobStep.textContent = job.step || "等待";
  jobMessage.textContent = job.message || "尚未开始转写。";
  updateSteps(progress, job.state);

  if (job.state === "succeeded") {
    stopPolling();
    loadTranscript(job.meeting_id);
    loadFiles();
  }
  if (job.state === "failed") {
    stopPolling();
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function startPolling(meetingId) {
  stopPolling();
  pollTimer = setInterval(async () => {
    try {
      const job = await requestJson(`/api/jobs/${encodeURIComponent(meetingId)}`);
      applyJob(job);
    } catch (error) {
      jobMessage.textContent = error.message;
    }
  }, 1500);
}

async function selectAudio(file) {
  selectedMeetingId = file.meeting_id;
  selectedFileName = file.name;
  activeMeeting.textContent = file.name;
  previewMeta.textContent = "等待转换结果";
  previewContent.textContent = "点击“开始转写”后，完成的文字稿会显示在这里。";
  const job = await requestJson(`/api/jobs/${encodeURIComponent(file.meeting_id)}`);
  applyJob(job);
  if (job.transcript_exists) {
    await loadTranscript(file.meeting_id);
  }
}

async function startTranscription(file) {
  await selectAudio(file);
  setStatus(`已开始转写 ${file.name}`);
  const job = await requestJson(`/api/transcribe/${encodeURIComponent(file.meeting_id)}`, { method: "POST" });
  applyJob(job);
  startPolling(file.meeting_id);
}

async function loadTranscript(meetingId = selectedMeetingId) {
  if (!meetingId) return;
  try {
    const data = await requestJson(`/api/transcripts/${encodeURIComponent(meetingId)}`);
    previewMeta.textContent = `${meetingId}.md`;
    previewContent.textContent = data.content;
  } catch (error) {
    previewMeta.textContent = "暂无转写稿";
    previewContent.textContent = error.message;
  }
}

function renderAudioFiles(files, jobs = []) {
  const jobsByMeeting = new Map(jobs.map((job) => [job.meeting_id, job]));
  audioCount.textContent = String(files.length);
  audioList.innerHTML = "";
  if (!files.length) {
    renderEmpty(audioList, "还没有音频文件。");
    return;
  }

  for (const file of files) {
    const job = jobsByMeeting.get(file.meeting_id);
    const state = job?.state || "idle";
    const item = document.createElement("article");
    item.className = `file-item is-${state}`;
    item.innerHTML = `
      <div class="file-name"></div>
      <div class="file-meta">${formatBytes(file.size)} · ${formatTime(file.updated_at)}</div>
      <div class="file-state">${stateLabel(state)}</div>
      <div class="file-actions">
        <button type="button" data-action="select">查看</button>
        <button type="button" data-action="transcribe">${state === "running" ? "转换中" : "开始转写"}</button>
      </div>
    `;
    item.querySelector(".file-name").textContent = file.name;
    item.querySelector("[data-action='select']").addEventListener("click", () => {
      selectAudio(file).catch((error) => setStatus(error.message));
    });
    const transcribeButton = item.querySelector("[data-action='transcribe']");
    transcribeButton.disabled = state === "running" || state === "queued";
    transcribeButton.addEventListener("click", () => {
      startTranscription(file).catch((error) => setStatus(error.message));
    });
    audioList.append(item);
  }
}

async function loadFiles() {
  const files = await requestJson("/api/files");
  renderAudioFiles(files.audio, files.jobs);
  if (!selectedMeetingId && files.audio.length) {
    await selectAudio(files.audio[0]);
  }
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
    const uploaded = await requestJson(`/api/audio?filename=${encodeURIComponent(file.name)}`, {
      method: "POST",
      headers: { "Content-Type": "application/octet-stream" },
      body: file,
    });
    audioInput.value = "";
    setStatus("音频已上传。");
    await loadFiles();
    selectedMeetingId = uploaded.meeting_id;
    selectedFileName = uploaded.name;
    activeMeeting.textContent = uploaded.name;
  } catch (error) {
    setStatus(error.message);
  }
});

refreshButton.addEventListener("click", () => {
  loadFiles().catch((error) => setStatus(error.message));
});

reloadResultButton.addEventListener("click", () => {
  loadTranscript().catch((error) => setStatus(error.message));
});

loadFiles().catch((error) => setStatus(error.message));
