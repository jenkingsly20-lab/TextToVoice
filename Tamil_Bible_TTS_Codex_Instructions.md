# Codex Implementation Brief — Tamil Bible TTS Voice Lab

## Mission
Build a working **local-first Windows 11 web application** to evaluate Tamil Bible text-to-speech quality using multiple interchangeable open-source TTS engines. The immediate goal is **listen and compare pronunciation**, not bulk-generate the Bible or deploy a service. Implement the project in the user's VS Code workspace, with documented commands and automated checks.

## Target hardware and environment
- ASUS ProArt Studiobook H7604JV
- Windows 11 Home (64-bit)
- Intel Core i9-13980HX
- 64 GB RAM
- NVIDIA GeForce RTX 4060 Laptop GPU, 8 GB VRAM
- ~447 GB free storage at time of planning
- Python application with **Gradio** browser UI, running at `127.0.0.1` only by default
- PyTorch CUDA when supported; CPU fallback and explicit error messages
- No Docker, Linux/WSL, Spring Boot, cloud inference, paid APIs, or deployment required for the initial trial.

## Critical research and verification gate
Before installing or writing engine-specific integration, inspect the **current official Hugging Face model cards and repositories** for IndicF5 and Indic-Speak, plus their authoritative inference examples. Verify: exact repository IDs; whether **Tamil is explicitly supported**; licenses (model weights AND code); dependencies and compatible Python/PyTorch versions; reference-audio requirements; available voices; CUDA/Windows support; download sizes and 8 GB VRAM feasibility; and whether commercial/distribution use is permitted. Record links, findings, and uncertainty in `docs/MODEL_RESEARCH.md`.

**Do not assume either model runs on Windows or fits 8 GB VRAM. Do not assert a voice count, licensing terms, offline operation, or production suitability without verification.** If native Windows support is unconfirmed, propose a Windows-compatible workaround or an alternative Tamil-capable open-source TTS model, but do not silently substitute models. If downloading or installing models requires user acceptance of licenses, gated access, or unusually large downloads, ask before proceeding. Start with the easiest *verified* Tamil-capable model; add other engines only after the first produces playable audio.

## Product scope — MVP
1. A polished, responsive local Gradio interface titled **Tamil Bible Voice Lab**.
2. Large Unicode Tamil textbox: paste one verse, multiple verses, or a whole short chapter; retain line breaks and punctuation. UTF-8 `.txt` upload is optional but desirable. Never silently modify scripture wording.
3. Model dropdown listing only **installed and usable** engines. Show other researched engines as "Not installed" with installation guidance rather than a broken selectable option.
4. For engines that support it, voice dropdown and reference-audio upload with a clearly labeled reference transcript input. For engines without multiple voices, explain the limitation. No unconsented voice cloning.
5. `Generate Speech` button; generation progress/status; cancellation where practical; friendly failures including out-of-memory, unsupported model, and invalid reference audio.
6. Embedded audio player and downloadable **MP3**. Generate PCM WAV internally if necessary, then encode MP3 via a locally installed FFmpeg binary (document installation and licensing). Preserve the WAV option for troubleshooting.
7. Compare two model outputs for identical text in separate players, with metadata: engine, voice/reference, elapsed generation time, audio duration, approximate speed factor, GPU/CPU, and output size. Do not claim an objective pronunciation score.
8. Manual assessment form: pronunciation correctness, biblical-name correctness, naturalness, pacing, omissions/insertions, overall preference; notes and optional export to CSV/JSON.
9. Save generated files and metadata locally under a configurable `outputs/` folder. Never overwrite previous output; use safe filenames and IDs. Do not transmit scripture or audio to third-party services.
10. Show GPU detection and current CUDA availability in a diagnostics panel; give exact commands to troubleshoot GPU detection.

## Engine architecture
- Implement a common `TTSEngine` protocol/interface: `id`, `display_name`, `capabilities`, `is_available()`, `load()`, `synthesize(text, options) -> audio result`, `unload()`.
- Separate adapters under `engines/`; isolate model-specific dependencies and avoid importing optional libraries until that engine is selected.
- Prefer a subprocess or isolated environment for conflicting engine dependencies; document the tradeoff.
- Load one large model at a time; release model and CUDA cache when switching; avoid loading both simultaneously on 8 GB VRAM.
- Detect CUDA, choose appropriate dtype only if officially supported, and handle CUDA OOM by offering shorter chunks / CPU fallback. Never promise a specific speed.
- Make downloads explicit, cached in a documented local directory, and avoid redownloading models at each launch. Respect model licenses and Hugging Face terms.
- Keep a small, dependency-light **mock engine** that produces a short test tone or silence, clearly labeled **TEST ONLY — NOT SPEECH**, so UI tests run without any model downloads.

## Text processing and audio
- Normalize only invisible formatting characters if necessary; retain original scripture exactly for display and comparison. Tamil UTF-8 and combining marks must work correctly.
- Support optional line-based chunking and conservative sentence splitting for memory safety. Avoid splitting inside Tamil grapheme clusters; do not split arbitrarily in the middle of words.
- Make pauses between chunks configurable (e.g. 250–700 ms) and preserve ordering.
- For MP3, combine PCM chunks first and encode the final file once to reduce timestamp drift. Do not concatenate independently encoded MP3 bytes.
- Provide a reproducible record of input text, model ID/version, settings, chunk boundaries, generated duration, and warnings.
- **Do not implement verse highlighting in the MVP**, but prepare an optional future output format: one chapter MP3 and `manifest.json` with `verse_number`, `start_ms`, `end_ms`. For accurate verse boundaries, ingest structured verse-numbered input and derive timestamps from the final PCM concatenation, including pauses. Avoid falsely claiming precise timings if an engine adds silence or trims output unexpectedly.

## Suggested structure
```
tamil-bible-tts-lab/
  app.py
  requirements.txt (or pyproject.toml)
  README.md
  .gitignore
  .env.example
  config.py
  engines/
    base.py
    registry.py
    mock.py
    indicf5.py       # only when verified
    indic_speak.py   # only when verified
  services/
    audio.py
    text_chunks.py
    gpu.py
    metadata.py
  tests/
    test_chunks.py
    test_audio.py
    test_registry.py
    test_ui_smoke.py
  docs/
    MODEL_RESEARCH.md
    WINDOWS_SETUP.md
    TROUBLESHOOTING.md
  outputs/          # gitignored
  model_cache/      # gitignored
```
Adjust structure where beneficial; keep it readable and maintainable.

## Implementation sequence
**Phase 1 — Research and scaffold**: Verify model support and licensing. Create project, Gradio UI, model registry, mock engine, local output handling, and test coverage. Show a working local UI even without downloaded models.

**Phase 2 — Real Tamil voice**: Install and integrate **one verified Tamil-capable engine** on the RTX 4060. Run short Tamil test sentences, record VRAM usage and speed, and produce valid WAV/MP3. If IndicF5 is verified compatible, prioritize it; otherwise document why another model was chosen.

**Phase 3 — Comparison**: Add a second verified model, with isolation for conflicting dependencies. Provide side-by-side A/B listening and manual rating export.

**Phase 4 — Optional future enhancement (NOT required now)**: Verse-numbered text import, chapter audio export, verse timing manifest, and Flutter integration contract. Do not begin full-Bible generation until human listening tests pass.

## Sample Tamil evaluation text
Use short tests, then expand. Ensure the UI handles names and distinctive Tamil sounds. User can paste their licensed Bible translation; do not bundle copyrighted translation data.

- `ஆதியிலே தேவன் வானத்தையும் பூமியையும் சிருஷ்டித்தார்.`
- `கர்த்தர் என் மேய்ப்பராயிருக்கிறார்; நான் தாழ்ச்சியடையேன்.`
- `இயேசு கிறிஸ்து`, `எருசலேம்`, `பெத்லகேம்`, `நேபுகாத்நேச்சார்`
- Pronunciation-focused: `தமிழ்`, `வாழ்வு`, `அறிவு`, `அருள்`, `பள்ளி`, `நன்றி`

Check omissions, repeated syllables, phoneme accuracy (ழ / ள / ல, ற / ர, ண / ந / ன), biblical names, natural phrasing, and sentence breaks.

## Windows setup expectations
- Give exact PowerShell commands to create/activate a Python virtual environment, install a **verified compatible CUDA-enabled PyTorch build**, verify `torch.cuda.is_available()`, install app dependencies, install FFmpeg, and run `python app.py`.
- Prefer stable pinned dependency ranges; **do not guess** PyTorch/CUDA/model-specific version compatibility. Check actual installed NVIDIA driver via `nvidia-smi` and current upstream instructions.
- Bind Gradio to `127.0.0.1` by default. Never set `share=True`. No telemetry or remote endpoints beyond intentional initial model/package downloads.
- Include a reproducible dependency file and a clear model download/cache procedure.
- Explain Windows Defender / firewall prompts without requiring insecure changes.

## Testing and acceptance criteria
- `python app.py` starts and opens the UI locally.
- Tamil pasted text renders and persists correctly; Unicode is not corrupted.
- Model selector accurately reflects installed engines.
- With a verified real engine, a 1–3 sentence Tamil sample generates audible speech; user can play it and download a valid MP3.
- Outputs include metadata; no silent text substitutions.
- GPU diagnostics accurately report RTX 4060 CUDA status or actionable error.
- Errors are displayed in the UI, not hidden in logs; no crashes when switching engines or when VRAM is insufficient.
- UI and core audio tests run without downloading large models.
- User can rate and compare results from two available engines, or the UI clearly says only one is installed.
- Provide a concise completion report with exact files created, commands executed, test results, known limitations, and next steps.

## Guardrails
- No paid API calls, no cloud TTS, no background server deployment, and no full Bible corpus processing during this prototype.
- Avoid claiming the generated speech is accurate without human review.
- Verify redistribution rights for source scripture text and generated audio before any public release.
- Do not commit model weights, user text, generated audio, or private reference recordings to Git.
- Ask before large downloads, environment-wide modifications, or any action requiring admin rights.

## Codex instruction
**Start now by researching the model cards and confirming the actual compatibility constraints. Then implement Phase 1 and Phase 2 end to end in this workspace. Do not stop at a design document or pseudocode. If model download, license acceptance, or driver access blocks Phase 2, finish a functioning Phase 1, report the precise blocker, and give the smallest next action needed.**
