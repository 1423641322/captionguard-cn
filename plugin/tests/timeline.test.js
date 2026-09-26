const assert = require("node:assert/strict");
const test = require("node:test");

const timeline = require("../timeline.js");

test("sanitizeFileName removes Windows-reserved characters", () => {
  assert.equal(timeline.sanitizeFileName('Interview: A/B? *'), "Interview_ A_B_ _");
});

test("joinNativePath preserves native separator style", () => {
  assert.equal(timeline.joinNativePath("C:\\Temp\\", "audio.wav"), "C:\\Temp\\audio.wav");
  assert.equal(timeline.joinNativePath("/tmp/", "audio.wav"), "/tmp/audio.wav");
});

test("formatSeconds creates a readable time value", () => {
  assert.equal(timeline.formatSeconds(3661.234), "01:01:01.234");
});

test("ensureAudioExtension rejects a video export preset", () => {
  assert.throws(() => timeline.ensureAudioExtension("mp4"), /只导出音频/);
});

test("exportActiveSequenceAudio exports IN to OUT and returns the generated entry", async () => {
  const calls = [];
  const exportedFile = { isFile: true, name: "Interview-123.wav" };
  const sequence = {
    name: "Interview",
    getInPoint: async () => ({ seconds: 2 }),
    getOutPoint: async () => ({ seconds: 8 }),
    getEndTime: async () => ({ seconds: 20 }),
    getAudioTrackCount: async () => 2
  };
  const ppro = {
    Project: {
      getActiveProject: async () => ({ getActiveSequence: async () => sequence })
    },
    Constants: { ExportType: { IMMEDIATELY: "immediately" } },
    EncoderManager: {
      getExportFileExtension: async () => ".wav",
      getManager: () => ({
        exportSequence: async (...args) => {
          calls.push(args);
          return true;
        }
      })
    }
  };
  const folder = {
    nativePath: "C:\\Temp",
    getEntry: async () => exportedFile
  };
  const result = await timeline.exportActiveSequenceAudio({
    ppro,
    localFileSystem: { getTemporaryFolder: async () => folder },
    presetFile: { nativePath: "C:\\Presets\\wav.epr" },
    useInOut: true,
    now: () => 123
  });

  assert.equal(result.file, exportedFile);
  assert.equal(result.info.selectedDuration, 6);
  assert.equal(result.exportFull, false);
  assert.deepEqual(calls[0].slice(1), [
    "immediately",
    "C:\\Temp\\Interview-123.wav",
    "C:\\Presets\\wav.epr",
    false
  ]);
});

test("exportActiveSequenceAudio falls back to full sequence without valid points", async () => {
  let exportFull;
  const sequence = {
    name: "Full",
    getInPoint: async () => ({ seconds: 0 }),
    getOutPoint: async () => ({ seconds: 0 }),
    getEndTime: async () => ({ seconds: 12 }),
    getAudioTrackCount: async () => 1
  };
  const ppro = {
    Project: { getActiveProject: async () => ({ getActiveSequence: async () => sequence }) },
    Constants: { ExportType: { IMMEDIATELY: 1 } },
    EncoderManager: {
      getExportFileExtension: async () => "wav",
      getManager: () => ({
        exportSequence: async (_sequence, _type, _output, _preset, value) => {
          exportFull = value;
          return true;
        }
      })
    }
  };
  const folder = {
    nativePath: "/tmp",
    getEntry: async () => ({ isFile: true })
  };

  await timeline.exportActiveSequenceAudio({
    ppro,
    localFileSystem: { getTemporaryFolder: async () => folder },
    presetFile: { nativePath: "/preset/audio.epr" },
    useInOut: true,
    now: () => 1
  });
  assert.equal(exportFull, true);
});
