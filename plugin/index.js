const { entrypoints, storage } = require("uxp");
const ppro = require("premierepro");

const { localFileSystem, formats } = storage;
const timeline = globalThis.CaptionGuardTimeline;

const API_BASE = "http://127.0.0.1:8765";
const PRESET_TOKEN_KEY = "captionguard.audioPresetToken";
const COMMON_LANGUAGE_CODES = ["zh", "en", "yue", "ja", "ko"];
const COMMON_LANGUAGE_LABELS = {
  zh: "中文",
  en: "English",
  yue: "粤语 / Cantonese",
  ja: "日本語 / Japanese",
  ko: "한국어 / Korean"
};

let selectedAudio = null;
let selectedPreset = null;
let activeSequenceInfo = null;
let latestResult = null;
let busy = false;

function byId(id) {
  return document.getElementById(id);
}

function setServiceState(ok, message) {
  const badge = byId("service-badge");
  badge.textContent = ok ? "已连接" : "未连接";
  badge.className = ok ? "badge badge-success" : "badge badge-danger";
  byId("service-message").textContent = message;
}

function showError(message) {
  const element = byId("error-message");
  element.textContent = message;
  element.hidden = !message;
}

function updateButtons() {
  byId("transcribe").disabled = busy || !selectedAudio;
  byId("timeline-transcribe").disabled =
    busy || !selectedPreset || !activeSequenceInfo || activeSequenceInfo.audioTrackCount < 1;
  byId("choose-audio").disabled = busy;
  byId("choose-preset").disabled = busy;
  byId("refresh-sequence").disabled = busy;
}

function setBusy(value, message) {
  busy = value;
  byId("progress").hidden = !value;
  if (message) byId("progress-message").textContent = message;
  updateButtons();
}

async function checkService() {
  showError("");
  try {
    const response = await fetch(`${API_BASE}/health`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    setServiceState(true, `CaptionGuard CN ${data.version} 正在本机运行。`);
    return true;
  } catch (error) {
    setServiceState(false, "无法连接 127.0.0.1:8765，请先启动本地服务。");
    return false;
  }
}

function appendLanguageOption(parent, code, label) {
  const option = document.createElement("option");
  option.value = code;
  option.textContent = label;
  parent.appendChild(option);
}

async function loadLanguageOptions() {
  const select = byId("language");
  const selected = select.value || "auto";
  try {
    const response = await fetch(`${API_BASE}/v1/languages`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    const byCode = new Map(data.languages.map((item) => [item.code, item.name]));

    select.innerHTML = "";
    appendLanguageOption(select, "auto", "自动检测（多语言）");
    appendLanguageOption(select, "zh-en", "中文 + English 混合增强");

    COMMON_LANGUAGE_CODES.forEach((code) => {
      if (byCode.has(code)) appendLanguageOption(select, code, COMMON_LANGUAGE_LABELS[code]);
    });

    data.languages.forEach(({ code, name }) => {
      if (!COMMON_LANGUAGE_CODES.includes(code)) {
        appendLanguageOption(select, code, `${name} (${code})`);
      }
    });
    select.value = selected === "auto" || selected === "zh-en" || byCode.has(selected)
      ? selected
      : "auto";
  } catch (_) {
    // Keep the built-in common-language choices when the local service is unavailable.
  }
}

async function refreshSequence() {
  try {
    activeSequenceInfo = await timeline.getActiveSequenceInfo(ppro);
    byId("sequence-name").textContent =
      `${activeSequenceInfo.name} · ${activeSequenceInfo.audioTrackCount} 条音频轨`;
    if (activeSequenceInfo.hasInOut) {
      byId("sequence-range").textContent =
        `入出点 ${timeline.formatSeconds(activeSequenceInfo.inSeconds)} – ` +
        `${timeline.formatSeconds(activeSequenceInfo.outSeconds)}，` +
        `时长 ${timeline.formatSeconds(activeSequenceInfo.selectedDuration)}`;
      byId("use-in-out").disabled = false;
    } else {
      byId("sequence-range").textContent =
        `未检测到有效入出点，将导出完整序列（${timeline.formatSeconds(activeSequenceInfo.endSeconds)}）。`;
      byId("use-in-out").disabled = true;
    }
  } catch (error) {
    activeSequenceInfo = null;
    byId("sequence-name").textContent = "没有可用的活动序列";
    byId("sequence-range").textContent = error.message || String(error);
    byId("use-in-out").disabled = true;
  }
  updateButtons();
}

function setPreset(file) {
  selectedPreset = file;
  byId("preset-name").textContent = file ? file.name : "尚未选择导出预设";
  updateButtons();
}

async function restorePreset() {
  const token = localStorage.getItem(PRESET_TOKEN_KEY);
  if (!token) return;
  try {
    const file = await localFileSystem.getEntryForPersistentToken(token);
    if (file && file.isFile) setPreset(file);
  } catch (error) {
    localStorage.removeItem(PRESET_TOKEN_KEY);
    setPreset(null);
  }
}

async function choosePreset() {
  showError("");
  const file = await localFileSystem.getFileForOpening({
    allowMultiple: false,
    types: ["epr"]
  });
  if (!file) return;
  setPreset(file);
  try {
    const token = await localFileSystem.createPersistentToken(file);
    localStorage.setItem(PRESET_TOKEN_KEY, token);
  } catch (error) {
    byId("preset-name").textContent = `${file.name}（本次会话）`;
  }
}

async function chooseAudio() {
  showError("");
  const file = await localFileSystem.getFileForOpening({
    allowMultiple: false,
    types: ["wav", "mp3", "m4a", "aac", "flac", "ogg", "mp4", "mov"]
  });
  if (!file) return;
  selectedAudio = file;
  byId("audio-name").textContent = file.name;
  updateButtons();
}

function parseGlossary(value) {
  const glossary = {};
  value.split(/\r?\n/).forEach((line) => {
    const separator = line.indexOf("=");
    if (separator <= 0) return;
    const source = line.slice(0, separator).trim();
    const target = line.slice(separator + 1).trim();
    if (source && target) glossary[source] = target;
  });
  return glossary;
}

function renderResults(result) {
  latestResult = result;
  byId("result-card").hidden = false;
  byId("result-summary").textContent = `${result.segments.length} 条 · ${result.review_count} 条待审`;
  const reviewList = byId("review-list");
  reviewList.innerHTML = "";

  const reviewed = result.segments.filter((segment) => segment.needs_review);
  if (reviewed.length === 0) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "没有发现低置信度或时长异常字幕。";
    reviewList.appendChild(empty);
    return;
  }

  reviewed.slice(0, 50).forEach((segment) => {
    const row = document.createElement("div");
    row.className = "review-row";
    const text = document.createElement("span");
    text.textContent = segment.text;
    const confidence = document.createElement("small");
    confidence.textContent = segment.confidence == null
      ? segment.review_reasons.join(" · ")
      : `置信度 ${Math.round(segment.confidence * 100)}%`;
    row.appendChild(text);
    row.appendChild(confidence);
    reviewList.appendChild(row);
  });
}

async function requestTranscription(file) {
  const data = await file.read({ format: formats.binary });
  const form = new FormData();
  form.append("file", data, file.name);
  form.append("language", byId("language").value);
  form.append("model_size", byId("model-size").value);
  form.append("max_chars", byId("max-chars").value);
  form.append("confidence_threshold", "0.72");
  form.append("glossary_json", JSON.stringify(parseGlossary(byId("glossary").value)));

  const response = await fetch(`${API_BASE}/v1/transcriptions`, {
    method: "POST",
    body: form
  });
  if (!response.ok) {
    let detail = `服务返回 HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch (_) {}
    throw new Error(detail);
  }
  return response.json();
}

async function transcribeSelectedAudio() {
  if (!selectedAudio || !(await checkService())) return;
  setBusy(true, "正在转写，请保持本地服务运行…");
  try {
    renderResults(await requestTranscription(selectedAudio));
  } catch (error) {
    showError(`转写失败：${error.message || error}`);
  } finally {
    setBusy(false);
  }
}

async function transcribeTimeline() {
  if (!selectedPreset || !(await checkService())) return;
  setBusy(true, "正在从 Premiere 时间线导出音频…");
  showError("");
  try {
    const exported = await timeline.exportActiveSequenceAudio({
      ppro,
      localFileSystem,
      presetFile: selectedPreset,
      useInOut: byId("use-in-out").checked
    });
    activeSequenceInfo = exported.info;
    selectedAudio = exported.file;
    byId("audio-name").textContent = `时间线导出：${exported.file.name}`;
    byId("progress-message").textContent = "音频导出完成，正在本地转写…";
    renderResults(await requestTranscription(exported.file));
  } catch (error) {
    showError(`时间线转写失败：${error.message || error}`);
  } finally {
    setBusy(false);
    await refreshSequence();
  }
}

async function saveSrt() {
  if (!latestResult) return;
  const baseName = selectedAudio ? selectedAudio.name.replace(/\.[^.]+$/, "") : "captions";
  const file = await localFileSystem.getFileForSaving(`${baseName}.srt`, { types: ["srt"] });
  if (!file) return;
  await file.write(latestResult.srt);
  showError("");
  byId("service-message").textContent = `已保存：${file.name}`;
}

async function initialize() {
  byId("check-service").addEventListener("click", checkService);
  byId("refresh-sequence").addEventListener("click", refreshSequence);
  byId("choose-preset").addEventListener("click", choosePreset);
  byId("timeline-transcribe").addEventListener("click", transcribeTimeline);
  byId("choose-audio").addEventListener("click", chooseAudio);
  byId("transcribe").addEventListener("click", transcribeSelectedAudio);
  byId("save-srt").addEventListener("click", saveSrt);
  updateButtons();
  await Promise.all([checkService(), loadLanguageOptions(), restorePreset(), refreshSequence()]);
}

entrypoints.setup({
  panels: {
    captionguardPanel: {
      create() {
        if (document.readyState === "loading") {
          document.addEventListener("DOMContentLoaded", initialize, { once: true });
        } else {
          initialize();
        }
      }
    }
  }
});
