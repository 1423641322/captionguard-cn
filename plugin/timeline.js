(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  } else {
    root.CaptionGuardTimeline = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  function sanitizeFileName(value) {
    const cleaned = String(value || "")
      .replace(/[<>:"/\\|?*\u0000-\u001f]/g, "_")
      .replace(/[. ]+$/g, "")
      .trim()
      .slice(0, 80);
    return cleaned || "sequence";
  }

  function normalizeExtension(value) {
    const extension = String(value || "").trim().replace(/^\.+/, "").toLowerCase();
    if (!/^[a-z0-9]{1,10}$/.test(extension)) {
      throw new Error("导出预设没有返回有效的文件扩展名。");
    }
    return extension;
  }

  function ensureAudioExtension(value) {
    const extension = normalizeExtension(value);
    const supported = ["wav", "mp3", "m4a", "aac", "flac", "ogg"];
    if (!supported.includes(extension)) {
      throw new Error(`所选 .epr 预设输出 .${extension}，请选择只导出音频的预设。`);
    }
    return extension;
  }

  function joinNativePath(folderPath, fileName) {
    const folder = String(folderPath || "").replace(/[\\/]+$/g, "");
    const separator = folder.includes("\\") || /^[a-z]:/i.test(folder) ? "\\" : "/";
    return `${folder}${separator}${fileName}`;
  }

  function formatSeconds(value) {
    const totalMilliseconds = Math.max(0, Math.round((Number(value) || 0) * 1000));
    const hours = Math.floor(totalMilliseconds / 3600000);
    const minutes = Math.floor((totalMilliseconds % 3600000) / 60000);
    const seconds = Math.floor((totalMilliseconds % 60000) / 1000);
    const milliseconds = totalMilliseconds % 1000;
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}.${String(milliseconds).padStart(3, "0")}`;
  }

  async function getActiveSequenceInfo(ppro) {
    const project = await ppro.Project.getActiveProject();
    if (!project) throw new Error("Premiere 中没有活动项目。");
    const sequence = await project.getActiveSequence();
    if (!sequence) throw new Error("请先在 Premiere 中打开一个序列。");

    const [inPoint, outPoint, endTime, audioTrackCount] = await Promise.all([
      sequence.getInPoint(),
      sequence.getOutPoint(),
      sequence.getEndTime(),
      sequence.getAudioTrackCount()
    ]);
    const inSeconds = Number(inPoint && inPoint.seconds) || 0;
    const outSeconds = Number(outPoint && outPoint.seconds) || 0;
    const endSeconds = Number(endTime && endTime.seconds) || 0;
    const hasInOut = outSeconds > inSeconds && outSeconds <= endSeconds + 0.001;

    return {
      project,
      sequence,
      name: sequence.name || "未命名序列",
      audioTrackCount,
      inSeconds,
      outSeconds,
      endSeconds,
      hasInOut,
      selectedDuration: hasInOut ? outSeconds - inSeconds : endSeconds
    };
  }

  function delay(milliseconds) {
    return new Promise((resolve) => setTimeout(resolve, milliseconds));
  }

  async function waitForEntry(folder, fileName, options) {
    const attempts = (options && options.attempts) || 20;
    const delayMilliseconds = (options && options.delayMilliseconds) || 250;
    const wait = (options && options.delay) || delay;
    let lastError;
    for (let attempt = 0; attempt < attempts; attempt += 1) {
      try {
        const entry = await folder.getEntry(fileName);
        if (entry && entry.isFile) return entry;
      } catch (error) {
        lastError = error;
      }
      await wait(delayMilliseconds);
    }
    throw new Error(`导出完成，但无法读取临时音频文件：${lastError || fileName}`);
  }

  async function exportActiveSequenceAudio(options) {
    const { ppro, localFileSystem, presetFile } = options;
    if (!presetFile || !presetFile.nativePath) {
      throw new Error("请先选择 Adobe Media Encoder 音频预设（.epr）。");
    }

    const info = await getActiveSequenceInfo(ppro);
    if (info.audioTrackCount < 1) throw new Error("当前序列没有音频轨道。");

    const extension = ensureAudioExtension(
      await ppro.EncoderManager.getExportFileExtension(info.sequence, presetFile.nativePath)
    );
    const tempFolder = await localFileSystem.getTemporaryFolder();
    const timestamp = options.now ? options.now() : Date.now();
    const fileName = `${sanitizeFileName(info.name)}-${timestamp}.${extension}`;
    const outputPath = joinNativePath(tempFolder.nativePath, fileName);
    const exportFull = !(options.useInOut && info.hasInOut);
    const encoder = ppro.EncoderManager.getManager();
    const started = await encoder.exportSequence(
      info.sequence,
      ppro.Constants.ExportType.IMMEDIATELY,
      outputPath,
      presetFile.nativePath,
      exportFull
    );
    if (!started) throw new Error("Premiere 未能启动音频导出，请检查导出预设。");

    const file = await waitForEntry(tempFolder, fileName, options.waitOptions);
    return { file, info, outputPath, exportFull };
  }

  return {
    exportActiveSequenceAudio,
    ensureAudioExtension,
    formatSeconds,
    getActiveSequenceInfo,
    joinNativePath,
    normalizeExtension,
    sanitizeFileName,
    waitForEntry
  };
});
