# Tamil Bible Voice Lab

**Chapter export update:** new generations permanently save MP3 + matching JSON only. Supply a chapter reference heading and one numbered verse per line for chapter filenames (e.g. `1john_02.mp3/json`) and actual audio-segment verse timestamps. Main UI provides both downloads. Default MP3 is 192 kbps; JSON and incremental local logs include detailed performance stages. See [chapter output/timing contract and manual checks](docs/CHAPTER_MP3_AND_TIMING.md). Older WAV-related notes below describe the earlier version. Flutter must honor MP3 encoder delay/padding; the JSON marks timing unavailable when verification cannot establish that timeline.

Local Windows Gradio app for comparing Tamil TTS pronunciation. **IndicF5 is installed and native Windows / CUDA generation has passed on the RTX 4060.** Human pronunciation review is still required. A second real speech engine is not installed.

## Status: the whole Bible in Tamil and English (completed 2026-10-22)

| Set | Chapters | Audio | Folder |
|---|---|---|---|
| Tamil (IndicF5, GPU) | 1,189 | 88.5 h | `outputs\batch\<book>\` |
| English, World English Bible (Kokoro-82M, GPU) | 1,189 | 76.3 h | `outputs\batch_en\<book>\` |

Each chapter is an MP3 plus a JSON file with verse timings, and each book has an `index.json`. Every set was checked against its database with `tools\verify_batch.py`.

## Fast generation and whole-book batches

Tamil generation is about 7× faster than the first version: about **3 seconds per verse**, or **about 2 minutes per chapter**, on the RTX 4060 laptop GPU. English (Kokoro on the GPU) runs at about 10× real time. Verses are read one sentence at a time, with real pauses at full stops and semicolons. Male English verses are read whole.

```powershell
.\.venv\Scripts\python.exe batch_generate.py --list-books
# Tamil
.\.venv\Scripts\python.exe batch_generate.py --books nt --voices male,female
.\.venv\Scripts\python.exe batch_generate.py --books genesis,psalms,ot --voices male,female --voice-for psalms=male
# English (WEB)
.\.venv\Scripts\python.exe batch_generate.py --language en --books nt --voices male,female
# Check a finished run (same arguments as the run)
.\.venv\Scripts\python.exe tools\verify_batch.py --language en --books nt --voices male,female
```

- Press **Ctrl+C once** to stop after the current chapter, or **twice** to stop immediately. Run the same command again to resume; finished chapters are never overwritten.
- Only one run per output folder is allowed. The batch keeps Windows awake while it runs.

See **[Speed improvements and batch generation](docs/PERFORMANCE_AND_BATCH.md)** for:
- the project status and the exact commands used;
- all implementation details and fixes, and the lessons learned;
- voices and how to add one;
- **the step-by-step runbook for adding another language**;
- verification, environments and tuning settings.

Notes for the app (Flutter) team are in [`handoff/`](handoff/).

## Using the app

Start from PowerShell in this folder:

```powershell
.\.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:7860, paste Tamil text and click **Generate Speech**. The app automatically uses the configured Tamil narration voice and matching transcript. Play the result or download MP3. No microphone, reference upload, transcript entry or consent checkbox is needed for this default workflow. Ready, Generating, Completed and error states are shown.

Advanced Settings starts collapsed. It retains UTF-8 upload, engine/device/chunk controls, WAV/metadata downloads and optional custom voice experiments. Explicitly enable custom voice to use your own authorized recording; stale hidden recordings are ignored otherwise. Retain output A as B in Compare to evaluate two takes of the same text. No speech is produced by the optional TEST ONLY tone engine.

The default is the publisher's licensed Rasa Tamil female book-narration sample `TAM_F_BOOK_00014` (5.066 seconds), supplied with its exact source transcript, hashes and [attribution](assets/voices/default_tamil/ATTRIBUTION.md). It is validated at startup and its PCM preprocessing is cached. Restore from the bundled assets, or explicitly run `install_default_voice.py` once after accepting Rasa dataset access; normal launches require no download. `TAMIL_TTS_DEFAULT_VOICE_CONFIG` can select a different documented local voice configuration. Human pronunciation and completeness review remain required.

Numbers now default to Tamil cardinal words (`123` → `நூற்று இருபத்து மூன்று`). Common punctuation becomes timed audio pauses. Original scripture stays unchanged, while normalized TTS input and every transformation are logged. Only explicitly selected **Verse-numbered Bible text** format omits validated line-leading verse labels; plain-text leading counts are retained and spoken. See [speech normalization](docs/SPEECH_NORMALIZATION.md) for format rules, preview and supported numeric forms.

The app preserves original wording, stores local unique output folders, disables Gradio analytics and model telemetry, and uses no cloud TTS. IndicF5 inference runs with Hugging Face offline mode in `.venv-indicf5` via a persistent subprocess. All necessary weights/vocoder artifacts are cached. No downloads occur at inference. Switching to the tone unloads the model. CPU is functional as a selectable option but its performance has not been benchmarked.

Files: `app.py` UI; `config.py` paths/privacy; `engines/` protocol, registry and mock; `services/` chunking, PCM/MP3, provenance, diagnostics and rating export; `tests/test_core.py` automated checks; `requirements-lock.txt` exact installed environment; `start.ps1` launcher.

See [model findings](docs/MODEL_RESEARCH.md), [Windows setup](docs/WINDOWS_SETUP.md), [troubleshooting](docs/TROUBLESHOOTING.md), and [completion report](docs/COMPLETION.md). No full Bible dataset is included. Supply text you may use; assess pronunciation manually before publishing generated material.
