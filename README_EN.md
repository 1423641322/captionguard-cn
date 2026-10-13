# CaptionGuard CN

[中文说明](README.md)

CaptionGuard CN is a local-first, multilingual caption workspace for Adobe Premiere Pro. The
repository contains:

- `plugin/`: a UXP panel for Premiere Pro 25.6 and later;
- `backend/`: a Python transcription service that listens only on the local computer;
- `tests/`: tests for language-aware caption splitting, glossary replacement, confidence review,
  and SRT output.

The current workflow can:

1. Read the active Premiere sequence, audio-track count, and In/Out range;
2. Export either the full sequence or its In/Out range with a user-selected Adobe Media Encoder
   audio-only `.epr` preset;
3. Send the exported audio to the local service, or accept an existing audio file;
4. Generate timestamped captions with `faster-whisper`;
5. Apply glossary replacements, language-aware line breaking, and low-confidence review flags;
6. Preview the results in the panel and save a standard `.srt` file.

Language features:

- Manual selection of all 100 languages supported by Whisper;
- Per-segment language detection in **Auto Detect (Multilingual)** mode;
- A dedicated **Chinese + English Mixed** mode with per-segment detection and a bilingual prompt;
- Automatic caption lengths: 20 characters for Chinese, 42 for English and most space-delimited
  languages, and 32 for mixed Chinese-English content;
- English-aware splitting at sentence punctuation and word boundaries while preserving spacing.

## End users: download only the EXE (recommended)

End users only need the released `CaptionGuard-CN.exe`. Python and UXP Developer Tool are not
required. The EXE contains both the local transcription service and the Premiere UXP plug-in
installer, and it remains available from the Windows system tray while running.

1. Download and run `CaptionGuard-CN.exe` from
   [GitHub Releases](https://github.com/1423641322/captionguard-cn/releases/latest);
2. Find the CaptionGuard icon in the Windows system tray;
3. Right-click it and choose **Install Premiere plug-in**;
4. Confirm the installation in Adobe Creative Cloud Desktop;
5. Restart Premiere, then open **Window → UXP Plugins → CaptionGuard CN**;
6. Keep `CaptionGuard-CN.exe` running in the background while using the panel.

The first transcription with a selected Whisper model requires an internet connection to download
that model. Later transcription can run locally after the download is complete. The tray menu also
lets you check the service, reinstall the Premiere plug-in, enable startup with Windows, or exit.
If the panel does not update after a software upgrade, reinstall it from the tray menu.

CaptionGuard has two parts that must work together: the UXP panel supplies the Premiere interface,
while the EXE performs local transcription. Even after the panel is installed, the EXE or the
development Python service must remain running during transcription.

## Requirements

- Windows 10 or 11;
- Adobe Premiere Pro 25.6 or later;
- Adobe Creative Cloud Desktop for installing the released plug-in;
- An internet connection for the first download of each Whisper model.

Source development additionally requires Python 3.11 or later and UXP Developer Tool 2.2 or later.

## Start the local service from source

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,asr]"
captionguard-server
```

The selected Whisper model is downloaded on first use. The service listens only on
`127.0.0.1:8765`; its health endpoint is `http://127.0.0.1:8765/health`.

To run the tests that do not require a model:

```powershell
python -m pip install -e ".[dev]"
pytest
node --test plugin/tests/timeline.test.js
```

## Developers: load with UXP Developer Tool

Instead of installing the released `.ccx`, developers can load the `plugin/` source directly with
UXP Developer Tool. UXP Developer Tool only loads the panel; the EXE or Python service is still
required for transcription.

1. Enable developer mode under **Premiere Settings → Plugins**, then restart Premiere;
2. Choose **Add Plugin** in UXP Developer Tool and open `plugin/manifest.json`;
3. Click **Load & Watch**;
4. Open **Window → UXP Plugins → CaptionGuard CN** in Premiere;
5. Run `CaptionGuard-CN.exe`, or start the Python service with the commands above;
6. Click **Check local service** in the panel;
7. Select an Adobe Media Encoder `.epr` preset that exports audio only;
8. Set optional In/Out points and click **Export timeline and transcribe**. Without a valid range,
   CaptionGuard exports the full sequence.

Do not keep the released CCX installed while loading the same development plug-in. Both use the
same plug-in ID and may create a duplicate panel or loading conflict. Uninstall the released plug-in
in Creative Cloud Desktop before switching to development mode. Before switching back, unload the
development copy in UXP Developer Tool.

After changing `manifest.json`, unload and add the plug-in again in UXP Developer Tool.

## Build the Windows release

Run the complete release build:

```powershell
.\scripts\build_release.ps1
```

The script builds the `.ccx`, then packages a standalone Python 3.12 runtime, the local service,
and the plug-in installer into `dist/CaptionGuard-CN.exe`. The `.ccx` is embedded, so it does not
need to be distributed separately. On first launch, the EXE extracts its runtime under the current
user's local application-data directory.

## Current limitations

- Timeline export currently uses the sequence mix and cannot select individual audio tracks;
- CaptionGuard produces a standard SRT file that must be imported into Premiere manually;
- The local service currently uses HTTP and is intended for the same Windows computer;
- Incremental retranscription and protection of manually edited captions are planned for a later
  release.

## API

### `GET /health`

Returns the local service status and version.

### `GET /v1/languages`

Returns all Whisper languages exposed in the panel.

### `POST /v1/transcriptions`

The `multipart/form-data` fields are:

- `file`: the audio or video file;
- `language`: `auto`, `zh-en`, `zh`, `en`, or another supported language code;
- `model_size`: `small` by default;
- `max_chars`: maximum characters per caption, or `0` for a language-aware automatic value;
- `confidence_threshold`: threshold for low-confidence review flags;
- `glossary_json`: a JSON string map, for example `{"Open AI":"OpenAI"}`.

The response contains normalized caption segments, review flags, and the complete SRT text.

## License

Apache-2.0. Whisper models and FFmpeg retain their respective licenses.

